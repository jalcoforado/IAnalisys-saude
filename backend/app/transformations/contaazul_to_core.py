"""
Transformação STAGING → CORE para o Conta Azul.

Padrão por entidade (espelha clinicorp_to_core.py):
  1. Lê stg_ca_<entity> em batch
  2. Aplica mapper(raw_data) → dict tipado
  3. INSERT...ON DUPLICATE KEY UPDATE em core_ca_<entity>
  4. Retorna TransformResult (fetched, inserted, updated, errors)

Especificidades CA registradas em docs/11_CONTAAZUL_ENDPOINTS_CATALOG.md:
- Pessoas: perfis array → 3 booleans (cliente/fornecedor/transportadora)
- Status: usa EN (`status`) — `status_traduzido` tem bug (retorna RECEBIDO
  em conta a pagar). Tradução nossa em `_status_to_pt`.
- Eventos financeiros: 1 linha POR PARCELA (não por evento). Unifica
  receber+pagar com `tipo` discriminator.
- Rateio: explode produto cartesiano categorias × centros_de_custo do
  /buscar (que já vem achatado). 1cat+1cc = exato. Múltiplo = aproximado
  (valor dividido por N×M, marca is_aproximado=true).
- Pessoa órfã (cliente.id em parcela mas não em stg_ca_pessoas):
  lazy upsert em core_ca_pessoas com dados inline (id+nome) — 579 órfãos
  conhecidos da Parente.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Iterable

from sqlalchemy import delete, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core_contaazul import (
    CoreCaBaixas,
    CoreCaCategorias,
    CoreCaCategoriasDre,
    CoreCaCentrosCusto,
    CoreCaContasFinanceiras,
    CoreCaDreLinks,
    CoreCaEventosFinanceiros,
    CoreCaPessoas,
    CoreCaProdutos,
    CoreCaRateio,
    CoreCaServicos,
    CoreCaVendedores,
)
from app.models.staging_contaazul import (
    StgCaCategorias,
    StgCaCategoriasDre,
    StgCaCentrosCusto,
    StgCaContasFinanceiras,
    StgCaContasPagar,
    StgCaContasReceber,
    StgCaParcelasDetalhe,
    StgCaPessoas,
    StgCaProdutos,
    StgCaSaldosAtuais,
    StgCaServicos,
    StgCaVendedores,
)


# ── Helpers de coerção ──────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _str(value: Any, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if max_len and len(s) > max_len:
        s = s[:max_len]
    return s


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        v = value.lower()
        if v in ("true", "1", "yes", "sim"):
            return True
        if v in ("false", "0", "no", "nao", "não"):
            return False
    return None


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except (ValueError, TypeError):
        return None


def _parse_date(value: Any) -> date | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return None


# ── Spec genérico + helpers de upsert ───────────────────────────

@dataclass(frozen=True)
class TransformSpec:
    name: str
    staging_model: type
    core_model: type
    mapper: Callable[[dict], dict]


@dataclass
class TransformResult:
    entity: str
    fetched: int
    inserted: int
    updated: int
    errors: int


async def _existing_external_ids(
    db: AsyncSession, model: type, tenant_id: str, ids: Iterable[str],
) -> set[str]:
    ids_list = list(ids)
    if not ids_list:
        return set()
    result = await db.execute(
        select(model.external_id).where(
            model.tenant_id == tenant_id,
            model.external_id.in_(ids_list),
        )
    )
    return {row[0] for row in result}


async def _read_staging(
    db: AsyncSession, staging_model: type, tenant_id: str,
) -> list[tuple[str, dict, datetime | None]]:
    result = await db.execute(
        select(
            staging_model.external_id,
            staging_model.raw_data,
            staging_model.external_updated_at,
        ).where(staging_model.tenant_id == tenant_id)
    )
    return [(row[0], row[1] or {}, row[2]) for row in result]


async def transform_entity(
    db: AsyncSession, tenant_id: str, spec: TransformSpec,
) -> TransformResult:
    """Transform genérica para entidades 1:1 (cadastros)."""
    rows = await _read_staging(db, spec.staging_model, tenant_id)
    if not rows:
        return TransformResult(spec.name, 0, 0, 0, 0)

    core_rows: list[dict] = []
    errors = 0
    for external_id, raw, ext_updated in rows:
        try:
            mapped = spec.mapper(raw)
            mapped["tenant_id"] = tenant_id
            mapped["external_id"] = external_id
            mapped["external_updated_at"] = ext_updated
            core_rows.append(mapped)
        except Exception:
            errors += 1
            continue

    if not core_rows:
        return TransformResult(spec.name, len(rows), 0, 0, errors)

    existing = await _existing_external_ids(
        db, spec.core_model, tenant_id, (r["external_id"] for r in core_rows),
    )

    skip = {"tenant_id", "external_id", "created_at"}
    sample = core_rows[0]
    updatable = [k for k in sample.keys() if k not in skip]

    BATCH = 500
    for i in range(0, len(core_rows), BATCH):
        chunk = core_rows[i:i + BATCH]
        stmt = mysql_insert(spec.core_model).values(chunk)
        stmt = stmt.on_duplicate_key_update(
            **{k: getattr(stmt.inserted, k) for k in updatable}
        )
        await db.execute(stmt)
    await db.commit()

    inserted = sum(1 for r in core_rows if r["external_id"] not in existing)
    updated = len(core_rows) - inserted
    return TransformResult(spec.name, len(rows), inserted, updated, errors)


# ── Mappers das entidades estáticas ─────────────────────────────

def map_pessoas(raw: dict) -> dict:
    perfis = raw.get("perfis") or []
    if not isinstance(perfis, list):
        perfis = []
    perfis_upper = [str(p).upper() for p in perfis]
    return {
        "documento": _str(raw.get("documento"), 32),
        "nome": _str(raw.get("nome"), 500),
        "tipo_pessoa": _str(raw.get("tipo_pessoa"), 20),
        "is_cliente": "CLIENTE" in perfis_upper,
        "is_fornecedor": "FORNECEDOR" in perfis_upper,
        "is_transportadora": "TRANSPORTADORA" in perfis_upper,
        "email": _str(raw.get("email"), 255),
        "telefone": _str(raw.get("telefone"), 50),
        "ativo": _bool(raw.get("ativo")),
        "id_legado": _int(raw.get("id_legado")),
        "uuid_legado": _str(raw.get("uuid_legado"), 64),
        "is_deleted": False,
    }


def map_categorias(raw: dict) -> dict:
    return {
        "nome": _str(raw.get("nome"), 255),
        "tipo": _str(raw.get("tipo"), 20),
        "categoria_pai_external_id": _str(raw.get("categoria_pai"), 64),
        "entrada_dre": _str(raw.get("entrada_dre"), 100),
        "considera_custo_dre": _bool(raw.get("considera_custo_dre")),
        "versao": _int(raw.get("versao")),
        "is_deleted": False,
    }


def map_centros_custo(raw: dict) -> dict:
    return {
        "codigo": _str(raw.get("codigo"), 50),
        "nome": _str(raw.get("nome"), 255),
        "ativo": _bool(raw.get("ativo")),
        "is_deleted": False,
    }


def map_produtos(raw: dict) -> dict:
    return {
        "codigo": _str(raw.get("codigo") or raw.get("sku"), 50),
        "nome": _str(raw.get("nome"), 500),
        "tipo": _str(raw.get("tipo"), 20),
        "status": _str(raw.get("status"), 20),
        "valor_venda": _decimal(raw.get("valor_venda")),
        "custo_medio": _decimal(raw.get("custo_medio")),
        "saldo": _decimal(raw.get("saldo")),
        "ean": _str(raw.get("ean"), 50),
        "is_deleted": False,
    }


def map_servicos(raw: dict) -> dict:
    return {
        "codigo": _str(raw.get("codigo"), 50),
        "nome": _str(raw.get("nome"), 500),
        "descricao": _str(raw.get("descricao")),
        "preco": _decimal(raw.get("preco")),
        "custo": _decimal(raw.get("custo")),
        "status": _str(raw.get("status"), 20),
        "tipo_servico": _str(raw.get("tipo_servico"), 20),
        "is_deleted": False,
    }


def map_vendedores(raw: dict) -> dict:
    return {
        "nome": _str(raw.get("nome"), 255),
        "email": _str(raw.get("email"), 255),
        "is_deleted": False,
    }


def map_contas_financeiras(raw: dict) -> dict:
    """Mapper das contas financeiras (bancos cadastrados no CA).

    Saldo atual é populado em segundo passo (transform_contas_financeiras),
    pois vem de staging diferente (`stg_ca_saldos_atuais`).
    """
    return {
        "nome": _str(raw.get("nome"), 255),
        "banco": _str(raw.get("banco"), 255),
        "codigo_banco": _str(raw.get("codigo_banco"), 20),
        "agencia": _str(raw.get("agencia"), 50),
        "numero": _str(raw.get("numero"), 50),
        "tipo": _str(raw.get("tipo"), 30),
        "ativo": _bool(raw.get("ativo")),
        "conta_padrao": _bool(raw.get("conta_padrao")),
        "possui_config_boleto": _bool(raw.get("possui_config_boleto_bancario")),
        "is_deleted": False,
    }


# ── Specs estáticas ─────────────────────────────────────────────

STATIC_TRANSFORMS: tuple[TransformSpec, ...] = (
    TransformSpec("pessoas",       StgCaPessoas,       CoreCaPessoas,       map_pessoas),
    TransformSpec("categorias",    StgCaCategorias,    CoreCaCategorias,    map_categorias),
    TransformSpec("centros_custo", StgCaCentrosCusto,  CoreCaCentrosCusto,  map_centros_custo),
    TransformSpec("produtos",      StgCaProdutos,      CoreCaProdutos,      map_produtos),
    TransformSpec("servicos",      StgCaServicos,      CoreCaServicos,      map_servicos),
    TransformSpec("vendedores",    StgCaVendedores,    CoreCaVendedores,    map_vendedores),
)


_STATIC_BY_NAME: dict[str, TransformSpec] = {s.name: s for s in STATIC_TRANSFORMS}


def get_static_spec(name: str) -> TransformSpec:
    if name not in _STATIC_BY_NAME:
        valid = ", ".join(_STATIC_BY_NAME.keys())
        raise ValueError(f"Entidade estática CA desconhecida: '{name}'. Válidas: {valid}")
    return _STATIC_BY_NAME[name]


async def transform_static_entity(
    db: AsyncSession, tenant_id: str, name: str,
) -> TransformResult:
    return await transform_entity(db, tenant_id, get_static_spec(name))


async def transform_all_static(
    db: AsyncSession, tenant_id: str,
) -> list[TransformResult]:
    results: list[TransformResult] = []
    for spec in STATIC_TRANSFORMS:
        results.append(await transform_entity(db, tenant_id, spec))
    return results


# ── DRE (Fase 2) — achatar árvore recursiva + popular links N:N ─

def _flatten_dre_tree(
    raiz: dict, parent_id: str | None, root_id: str, nivel: int,
) -> list[tuple[dict, list[str]]]:
    """Achata recursivamente uma árvore DRE.

    Retorna lista de tuplas (no_mapped, [categoria_external_ids]) — a tupla
    contém dict pronto pra inserir em core_ca_categorias_dre + os IDs das
    categorias_financeiras planas vinculadas (links N:N).
    """
    out: list[tuple[dict, list[str]]] = []
    no_id = _str(raiz.get("id"), 64)
    if not no_id:
        return out

    cats_fin = raiz.get("categorias_financeiras") or []
    if not isinstance(cats_fin, list):
        cats_fin = []
    cat_ids = [_str(c.get("id"), 64) for c in cats_fin if isinstance(c, dict) and c.get("id")]
    cat_ids = [c for c in cat_ids if c]

    no = {
        "external_id": no_id,
        "descricao": _str(raiz.get("descricao"), 255),
        "codigo": _str(raiz.get("codigo"), 50),
        "posicao": _int(raiz.get("posicao")),
        "nivel": nivel,
        "parent_external_id": parent_id,
        "root_external_id": root_id,
        "indica_totalizador": _bool(raiz.get("indica_totalizador")),
        "representa_soma_custo_medio": _bool(raiz.get("representa_soma_custo_medio")),
        "qtd_categorias_financeiras": len(cat_ids),
        "is_deleted": False,
    }
    out.append((no, cat_ids))

    subitens = raiz.get("subitens") or []
    if isinstance(subitens, list):
        for sub in subitens:
            if isinstance(sub, dict):
                out.extend(_flatten_dre_tree(sub, no_id, root_id, nivel + 1))
    return out


async def transform_categorias_dre(
    db: AsyncSession, tenant_id: str,
) -> TransformResult:
    """Promove `stg_ca_categorias_dre` (16 raízes Parente) em
    `core_ca_categorias_dre` (achatado) + `core_ca_dre_links` (N:N).

    Estratégia: limpa os links do tenant e re-popula (idempotente, simples).
    Os nós DRE (1:1 por id) usam upsert normal.
    """
    raizes = await _read_staging(db, StgCaCategoriasDre, tenant_id)
    if not raizes:
        return TransformResult("categorias_dre", 0, 0, 0, 0)

    nodes: list[dict] = []
    links: list[tuple[str, str]] = []  # (dre_id, categoria_id)
    errors = 0
    for raiz_external_id, raw, _ in raizes:
        try:
            flat = _flatten_dre_tree(raw, parent_id=None, root_id=raiz_external_id, nivel=0)
            for no, cat_ids in flat:
                no["tenant_id"] = tenant_id
                nodes.append(no)
                for cid in cat_ids:
                    links.append((no["external_id"], cid))
        except Exception:
            errors += 1
            continue

    if not nodes:
        return TransformResult("categorias_dre", len(raizes), 0, 0, errors)

    existing = await _existing_external_ids(
        db, CoreCaCategoriasDre, tenant_id, (n["external_id"] for n in nodes),
    )

    skip = {"tenant_id", "external_id", "created_at"}
    updatable = [k for k in nodes[0].keys() if k not in skip]
    BATCH = 500
    for i in range(0, len(nodes), BATCH):
        chunk = nodes[i:i + BATCH]
        stmt = mysql_insert(CoreCaCategoriasDre).values(chunk)
        stmt = stmt.on_duplicate_key_update(
            **{k: getattr(stmt.inserted, k) for k in updatable}
        )
        await db.execute(stmt)

    # Re-popula links (delete + insert) — simples e idempotente
    await db.execute(
        delete(CoreCaDreLinks).where(CoreCaDreLinks.tenant_id == tenant_id)
    )
    if links:
        link_rows = [
            {"tenant_id": tenant_id, "dre_external_id": d, "categoria_external_id": c}
            for d, c in links
        ]
        for i in range(0, len(link_rows), BATCH):
            await db.execute(mysql_insert(CoreCaDreLinks).values(link_rows[i:i + BATCH]))

    await db.commit()
    inserted = sum(1 for n in nodes if n["external_id"] not in existing)
    updated = len(nodes) - inserted
    return TransformResult("categorias_dre", len(raizes), inserted, updated, errors)


# ── Baixas (Onda 2) — explode `baixas[]` da parcela em N rows ───

def _baixa_row(
    raw_parcela: dict,
    baixa: dict,
    parcela_external_id: str,
    tenant_id: str,
) -> dict | None:
    """Mapeia 1 baixa de dentro de raw_parcela.baixas[] em row de
    core_ca_baixas. raw_parcela tem o contexto (tipo, conta, etc) que a
    baixa individual não traz."""
    baixa_id = _str(baixa.get("id"), 64)
    if not baixa_id:
        return None

    evento = raw_parcela.get("evento") or {}
    tipo = _str(evento.get("tipo"), 20)  # RECEITA | DESPESA
    referencia = (evento.get("referencia") or {})
    origem = _str(referencia.get("origem"), 40)

    # `conta_financeira` da parcela (pode estar duplicada em cada baixa)
    conta = (raw_parcela.get("conta_financeira") or baixa.get("conta_financeira") or {})
    composicao = baixa.get("valor_composicao") or {}

    # Pessoa (cliente/fornecedor)
    pessoa = (raw_parcela.get("cliente") or raw_parcela.get("fornecedor") or {})

    return {
        "tenant_id": tenant_id,
        "external_id": baixa_id,
        "parcela_external_id": parcela_external_id,
        "evento_external_id": _str(evento.get("id"), 64),
        "is_deleted": False,
        "tipo": tipo,
        "data_pagamento": _parse_date(baixa.get("data_pagamento")),
        "data_vencimento": _parse_date(raw_parcela.get("data_vencimento")),
        "data_competencia": _parse_date(evento.get("data_competencia")),
        "metodo_pagamento": _str(raw_parcela.get("metodo_pagamento"), 60),
        "valor_pago": _decimal(baixa.get("valor_pago") or composicao.get("valor_liquido")),
        "valor_bruto": _decimal(composicao.get("valor_bruto")),
        "valor_liquido": _decimal(composicao.get("valor_liquido")),
        "multa": _decimal(composicao.get("multa")),
        "juros": _decimal(composicao.get("juros")),
        "desconto": _decimal(composicao.get("desconto")),
        "taxa": _decimal(composicao.get("taxa")),
        "conta_financeira_external_id": _str(conta.get("id"), 64),
        "conta_financeira_nome": _str(conta.get("nome"), 255),
        "conta_financeira_banco": _str(conta.get("banco"), 60),
        "conciliado": _bool(raw_parcela.get("conciliado")),
        "baixa_agendada": _bool(raw_parcela.get("baixa_agendada")),
        "origem_referencia": origem,
        "nsu": _str(baixa.get("nsu") or raw_parcela.get("nsu"), 60),
        "pessoa_external_id": _str(pessoa.get("id"), 64),
    }


async def transform_baixas(
    db: AsyncSession, tenant_id: str,
) -> TransformResult:
    """Promove `stg_ca_parcelas_detalhe` em `core_ca_baixas`.

    Cada parcela em staging tem `baixas[]` (1+) — explodimos em N rows
    em core_ca_baixas. Idempotente via UNIQUE(tenant_id, external_id da baixa).
    """
    rows = await _read_staging(db, StgCaParcelasDetalhe, tenant_id)
    if not rows:
        return TransformResult("baixas", 0, 0, 0, 0)

    core_rows: list[dict] = []
    errors = 0
    for parcela_external_id, raw, _ in rows:
        try:
            baixas = raw.get("baixas") or []
            if not isinstance(baixas, list):
                continue
            for baixa in baixas:
                if not isinstance(baixa, dict):
                    continue
                row = _baixa_row(raw, baixa, parcela_external_id, tenant_id)
                if row is not None:
                    core_rows.append(row)
        except Exception:
            errors += 1
            continue

    if not core_rows:
        return TransformResult("baixas", len(rows), 0, 0, errors)

    existing = await _existing_external_ids(
        db, CoreCaBaixas, tenant_id, (r["external_id"] for r in core_rows),
    )

    skip = {"tenant_id", "external_id", "created_at"}
    updatable = [k for k in core_rows[0].keys() if k not in skip]

    BATCH = 500
    for i in range(0, len(core_rows), BATCH):
        chunk = core_rows[i:i + BATCH]
        stmt = mysql_insert(CoreCaBaixas).values(chunk)
        stmt = stmt.on_duplicate_key_update(
            **{k: getattr(stmt.inserted, k) for k in updatable}
        )
        await db.execute(stmt)
    await db.commit()

    inserted = sum(1 for r in core_rows if r["external_id"] not in existing)
    updated = len(core_rows) - inserted
    return TransformResult("baixas", len(rows), inserted, updated, errors)


# ── Saldos bancários (Fase 1) — promo dedicada que junta 2 stagings ─

async def transform_contas_financeiras(
    db: AsyncSession, tenant_id: str,
) -> TransformResult:
    """Promove `stg_ca_contas_financeiras` + `stg_ca_saldos_atuais` em
    `core_ca_contas_financeiras` (1 linha por conta com saldo atual incluso).

    Saldo atual fica `None` se a chamada `/saldo-atual` falhou pra aquela
    conta no último sync (registro ausente no staging de saldos).
    """
    contas_rows = await _read_staging(db, StgCaContasFinanceiras, tenant_id)
    if not contas_rows:
        return TransformResult("contas_financeiras", 0, 0, 0, 0)

    saldos_rows = await _read_staging(db, StgCaSaldosAtuais, tenant_id)
    saldos_by_conta: dict[str, tuple[Decimal | None, datetime | None]] = {}
    for ext_id, raw, _ in saldos_rows:
        valor = _decimal((raw or {}).get("saldo_atual"))
        consultado = _parse_dt((raw or {}).get("consultado_em"))
        saldos_by_conta[ext_id] = (valor, consultado)

    core_rows: list[dict] = []
    errors = 0
    for external_id, raw, ext_updated in contas_rows:
        try:
            mapped = map_contas_financeiras(raw)
            mapped["tenant_id"] = tenant_id
            mapped["external_id"] = external_id
            mapped["external_updated_at"] = ext_updated
            saldo, consultado = saldos_by_conta.get(external_id, (None, None))
            mapped["saldo_atual"] = saldo
            mapped["saldo_atualizado_em"] = consultado
            core_rows.append(mapped)
        except Exception:
            errors += 1
            continue

    if not core_rows:
        return TransformResult("contas_financeiras", len(contas_rows), 0, 0, errors)

    existing = await _existing_external_ids(
        db, CoreCaContasFinanceiras, tenant_id, (r["external_id"] for r in core_rows),
    )

    skip = {"tenant_id", "external_id", "created_at"}
    updatable = [k for k in core_rows[0].keys() if k not in skip]

    BATCH = 500
    for i in range(0, len(core_rows), BATCH):
        chunk = core_rows[i:i + BATCH]
        stmt = mysql_insert(CoreCaContasFinanceiras).values(chunk)
        stmt = stmt.on_duplicate_key_update(
            **{k: getattr(stmt.inserted, k) for k in updatable}
        )
        await db.execute(stmt)
    await db.commit()

    inserted = sum(1 for r in core_rows if r["external_id"] not in existing)
    updated = len(core_rows) - inserted
    return TransformResult("contas_financeiras", len(contas_rows), inserted, updated, errors)


# ── Eventos financeiros + rateio (caso especial) ────────────────

# Tradução nossa (status_traduzido do CA tem bug em conta a pagar — retorna
# "RECEBIDO" em vez de "PAGO"). Mantemos status EN como verdade e geramos PT.
_STATUS_PT = {
    "ACQUITTED": "PAGO",
    "OVERDUE": "ATRASADO",
    "PENDING": "EM_ABERTO",
    "PARTIAL": "PAGO_PARCIAL",
    "DUE_TODAY": "VENCE_HOJE",
}


def _status_to_pt(status_en: str | None) -> str | None:
    if not status_en:
        return None
    return _STATUS_PT.get(status_en.upper(), status_en)


async def _lazy_upsert_pessoas_orfas(
    db: AsyncSession, tenant_id: str,
    inline_pessoas: dict[str, str],  # external_id → nome
) -> int:
    """Pra cada pessoa referenciada em parcelas mas ausente em core_ca_pessoas,
    cria um registro mínimo (id + nome). Retorna quantas foram criadas.

    Assume que core_ca_pessoas já recebeu transform_entity antes — só popula
    os órfãos. Idempotente via INSERT...ON DUPLICATE KEY (não atualiza nome
    se já existe).
    """
    if not inline_pessoas:
        return 0
    existing = await _existing_external_ids(
        db, CoreCaPessoas, tenant_id, inline_pessoas.keys()
    )
    novos = [
        {
            "tenant_id": tenant_id,
            "external_id": eid,
            "nome": (nome or "")[:500] or None,
            "is_cliente": False,
            "is_fornecedor": False,
            "is_transportadora": False,
            "is_deleted": False,
        }
        for eid, nome in inline_pessoas.items()
        if eid not in existing
    ]
    if not novos:
        return 0
    BATCH = 500
    for i in range(0, len(novos), BATCH):
        chunk = novos[i:i + BATCH]
        stmt = mysql_insert(CoreCaPessoas).values(chunk)
        # ON DUPLICATE KEY = no-op (não sobrescreve nome com placeholder)
        stmt = stmt.on_duplicate_key_update(external_id=stmt.inserted.external_id)
        await db.execute(stmt)
    await db.commit()
    return len(novos)


def _build_evento_row(
    raw: dict, external_id: str, ext_updated: datetime | None,
    tenant_id: str, tipo: str,
) -> dict | None:
    """Converte uma parcela do staging em row pra core_ca_eventos_financeiros."""
    if tipo == "RECEITA":
        pessoa = raw.get("cliente") or {}
    else:
        pessoa = raw.get("fornecedor") or {}
    cats = raw.get("categorias") or []
    ccs = raw.get("centros_de_custo") or []
    qtd_cats = len(cats) if isinstance(cats, list) else 0
    qtd_ccs = len(ccs) if isinstance(ccs, list) else 0

    status_en = _str(raw.get("status"), 30)
    return {
        "tenant_id": tenant_id,
        "external_id": external_id,
        "external_updated_at": ext_updated,
        "tipo": tipo,
        "descricao": _str(raw.get("descricao")),
        "status": status_en,
        "status_pt": _status_to_pt(status_en),
        "pessoa_external_id": _str((pessoa or {}).get("id"), 64),
        "pessoa_nome": _str((pessoa or {}).get("nome"), 500),
        "valor_total": _decimal(raw.get("total")),
        "valor_pago": _decimal(raw.get("pago")),
        "valor_em_aberto": _decimal(raw.get("nao_pago")),
        "data_vencimento": _parse_date(raw.get("data_vencimento")),
        "data_competencia": _parse_date(raw.get("data_competencia")),
        "data_criacao": _parse_dt(raw.get("data_criacao")),
        "evento_origem_id": _str((raw.get("evento") or {}).get("id"), 64),
        "tem_rateio_multiplo": qtd_cats > 1 or qtd_ccs > 1,
        "qtd_categorias": qtd_cats,
        "qtd_centros_custo": qtd_ccs,
        "is_deleted": False,
    }


def _build_rateio_rows(
    raw: dict, parcela_external_id: str, tenant_id: str,
) -> list[dict]:
    """Explode rateio em linhas. 1cat+1cc = exato. Múltiplo = produto
    cartesiano com valor dividido proporcionalmente (marca is_aproximado).
    1cat+0cc = 1 linha sem CC. 0cat = sem rateio (retorna []).
    """
    cats = raw.get("categorias") or []
    ccs = raw.get("centros_de_custo") or []
    if not isinstance(cats, list):
        cats = []
    if not isinstance(ccs, list):
        ccs = []
    valor_total = _decimal(raw.get("total")) or Decimal("0")

    if not cats:
        return []

    # 1 categoria + 0 centros — 1 linha sem CC
    if len(ccs) == 0:
        return [{
            "tenant_id": tenant_id,
            "evento_financeiro_external_id": parcela_external_id,
            "categoria_external_id": _str(cats[0].get("id"), 64),
            "centro_custo_external_id": None,
            "valor": valor_total if len(cats) == 1 else valor_total / len(cats),
            "is_aproximado": len(cats) > 1,
        }] + (
            [
                {
                    "tenant_id": tenant_id,
                    "evento_financeiro_external_id": parcela_external_id,
                    "categoria_external_id": _str(c.get("id"), 64),
                    "centro_custo_external_id": None,
                    "valor": valor_total / len(cats),
                    "is_aproximado": True,
                }
                for c in cats[1:]
            ]
        )

    # Caso simples: 1 categoria + 1 CC = exato
    if len(cats) == 1 and len(ccs) == 1:
        return [{
            "tenant_id": tenant_id,
            "evento_financeiro_external_id": parcela_external_id,
            "categoria_external_id": _str(cats[0].get("id"), 64),
            "centro_custo_external_id": _str(ccs[0].get("id"), 64),
            "valor": valor_total,
            "is_aproximado": False,
        }]

    # Caso complexo: produto cartesiano com valor dividido igual
    n_combos = len(cats) * len(ccs)
    valor_por = valor_total / n_combos if n_combos > 0 else Decimal("0")
    return [
        {
            "tenant_id": tenant_id,
            "evento_financeiro_external_id": parcela_external_id,
            "categoria_external_id": _str(c.get("id"), 64),
            "centro_custo_external_id": _str(cc.get("id"), 64),
            "valor": valor_por,
            "is_aproximado": True,
        }
        for c in cats for cc in ccs
    ]


async def transform_eventos_financeiros(
    db: AsyncSession, tenant_id: str,
) -> TransformResult:
    """Transforma stg_ca_contas_receber + stg_ca_contas_pagar em
    core_ca_eventos_financeiros (unificada com `tipo`) + core_ca_rateio.

    1. Lê ambos staging
    2. Monta rows com `tipo` discriminator
    3. Lazy upsert de pessoas órfãs (referenciadas inline mas ausentes em core_ca_pessoas)
    4. Upsert eventos
    5. DELETE+INSERT rateio (não tem chave natural pra upsert; reconstrói)
    """
    receber = await _read_staging(db, StgCaContasReceber, tenant_id)
    pagar = await _read_staging(db, StgCaContasPagar, tenant_id)
    total_fetched = len(receber) + len(pagar)
    if total_fetched == 0:
        return TransformResult("eventos_financeiros", 0, 0, 0, 0)

    # 1) Coleta inline de pessoas (cliente em receber, fornecedor em pagar)
    inline_pessoas: dict[str, str] = {}
    for _, raw, _ in receber:
        p = raw.get("cliente") or {}
        pid = p.get("id")
        if pid and pid not in inline_pessoas:
            inline_pessoas[pid] = p.get("nome") or ""
    for _, raw, _ in pagar:
        p = raw.get("fornecedor") or {}
        pid = p.get("id")
        if pid and pid not in inline_pessoas:
            inline_pessoas[pid] = p.get("nome") or ""

    await _lazy_upsert_pessoas_orfas(db, tenant_id, inline_pessoas)

    # 2) Monta rows de eventos
    event_rows: list[dict] = []
    rateio_rows_by_parcela: list[tuple[str, list[dict]]] = []
    errors = 0

    for external_id, raw, ext_updated in receber:
        try:
            row = _build_evento_row(raw, external_id, ext_updated, tenant_id, "RECEITA")
            if row:
                event_rows.append(row)
                rateio_rows_by_parcela.append(
                    (external_id, _build_rateio_rows(raw, external_id, tenant_id))
                )
        except Exception:
            errors += 1

    for external_id, raw, ext_updated in pagar:
        try:
            row = _build_evento_row(raw, external_id, ext_updated, tenant_id, "DESPESA")
            if row:
                event_rows.append(row)
                rateio_rows_by_parcela.append(
                    (external_id, _build_rateio_rows(raw, external_id, tenant_id))
                )
        except Exception:
            errors += 1

    if not event_rows:
        return TransformResult("eventos_financeiros", total_fetched, 0, 0, errors)

    # 3) Pre-query existentes pra contar inserted vs updated
    existing = await _existing_external_ids(
        db, CoreCaEventosFinanceiros, tenant_id, (r["external_id"] for r in event_rows),
    )

    # 4) Upsert eventos em batches
    skip = {"tenant_id", "external_id", "created_at"}
    sample = event_rows[0]
    updatable = [k for k in sample.keys() if k not in skip]
    BATCH = 500
    for i in range(0, len(event_rows), BATCH):
        chunk = event_rows[i:i + BATCH]
        stmt = mysql_insert(CoreCaEventosFinanceiros).values(chunk)
        stmt = stmt.on_duplicate_key_update(
            **{k: getattr(stmt.inserted, k) for k in updatable}
        )
        await db.execute(stmt)
    await db.commit()

    # 5) Reconstrói rateio: DELETE de tudo do tenant + INSERT
    # (não há chave natural pra upsert — produto cartesiano gera múltiplas
    # linhas por parcela. Reconstrução completa é mais simples e idempotente.)
    await db.execute(delete(CoreCaRateio).where(CoreCaRateio.tenant_id == tenant_id))

    all_rateio: list[dict] = []
    for _, rows in rateio_rows_by_parcela:
        all_rateio.extend(rows)

    if all_rateio:
        for i in range(0, len(all_rateio), BATCH):
            chunk = all_rateio[i:i + BATCH]
            await db.execute(mysql_insert(CoreCaRateio).values(chunk))
    await db.commit()

    inserted = sum(1 for r in event_rows if r["external_id"] not in existing)
    updated = len(event_rows) - inserted
    return TransformResult("eventos_financeiros", total_fetched, inserted, updated, errors)


# ── Orquestrador ────────────────────────────────────────────────

async def transform_all(
    db: AsyncSession, tenant_id: str,
) -> list[TransformResult]:
    """Roda transform de todas as entidades CA na ordem correta:
    cadastros (pessoas, categorias, etc.) → DRE (depende de categorias
    planas pros links) → eventos_financeiros (depende de pessoas pra
    resolver órfãos) → contas financeiras (saldos).
    """
    results = await transform_all_static(db, tenant_id)
    results.append(await transform_categorias_dre(db, tenant_id))
    results.append(await transform_eventos_financeiros(db, tenant_id))
    results.append(await transform_contas_financeiras(db, tenant_id))
    results.append(await transform_baixas(db, tenant_id))
    return results
