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
    CoreCaCategorias,
    CoreCaCentrosCusto,
    CoreCaEventosFinanceiros,
    CoreCaPessoas,
    CoreCaProdutos,
    CoreCaRateio,
    CoreCaServicos,
    CoreCaVendedores,
)
from app.models.staging_contaazul import (
    StgCaCategorias,
    StgCaCentrosCusto,
    StgCaContasPagar,
    StgCaContasReceber,
    StgCaPessoas,
    StgCaProdutos,
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
    cadastros (pessoas, categorias, etc.) → eventos_financeiros (depende
    de pessoas pra resolver órfãos).
    """
    results = await transform_all_static(db, tenant_id)
    results.append(await transform_eventos_financeiros(db, tenant_id))
    return results
