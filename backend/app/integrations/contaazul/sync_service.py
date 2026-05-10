"""
Serviço de sincronização Conta Azul → staging (record-level, idempotente).

Padrão por entidade (espelha sync_service.py do Clinicorp):
  1. Cria sync_jobs com status='running'
  2. Resolve token + renova automaticamente se expirado
  3. Pagina o endpoint via ContaAzulClient
  4. Para cada registro, faz INSERT ... ON DUPLICATE KEY UPDATE em stg_ca_*
  5. Atualiza sync_jobs (status, métricas, duração)
  6. Atualiza sync_checkpoints com a contagem real em staging

Idempotência: chave única (tenant_id, external_id). Re-rodar nunca duplica.

Estáticas (sem período): pessoas, produtos, servicos, vendedores.
Transacionais (por mês de vencimento): contas_receber, contas_pagar.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import bindparam, delete, func, select, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.contaazul.client import ContaAzulClient, ContaAzulError
from app.integrations.contaazul.oauth import refresh_access_token, ContaAzulOAuthError
from app.models.contaazul_token import ContaAzulToken
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
    StgCaSaldosIniciais,
    StgCaServicos,
    StgCaVendedores,
)
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_job import SyncJob


SOURCE = "contaazul"


# ── Helpers gerais ──────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_dt(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except (ValueError, TypeError):
        return None


def _period_bounds_full_month(year: int, month: int) -> tuple[date, date]:
    """Mês completo — Conta Azul aceita datas futuras (vencimentos pendentes)."""
    if not (1 <= month <= 12):
        raise ValueError(f"Mês inválido: {month}")
    from_date = date(year, month, 1)
    if month == 12:
        to_date = date(year, 12, 31)
    else:
        to_date = date(year, month + 1, 1) - timedelta(days=1)
    return from_date, to_date


# ── Token: obter cliente autenticado, renovando se preciso ──────

async def _get_authenticated_client(
    db: AsyncSession, tenant_id: str,
) -> ContaAzulClient:
    """Retorna ContaAzulClient com token vigente; renova se já expirou."""
    result = await db.execute(
        select(ContaAzulToken).where(ContaAzulToken.tenant_id == tenant_id)
    )
    token = result.scalar_one_or_none()
    if not token:
        raise ContaAzulError(
            "Conta Azul não conectada para este tenant. Acesse /empresa/integracoes."
        )

    # Se vai expirar nos próximos 60s, renova preventivamente.
    # CRÍTICO: o CA rotaciona refresh_token a cada uso. O novo precisa ser
    # commitado IMEDIATAMENTE no DB — se um rollback ocorrer depois (ex: erro
    # no sync), o refresh_token novo no CA fica sem par no DB e todo refresh
    # futuro retorna invalid_grant.
    if _now() >= token.expires_at - timedelta(seconds=60):
        try:
            new_data = await refresh_access_token(token.refresh_token)
        except ContaAzulOAuthError as exc:
            raise ContaAzulError(f"Falha ao renovar token: {exc}")
        token.access_token = new_data["access_token"]
        token.refresh_token = new_data["refresh_token"]
        token.expires_at = new_data["expires_at"]
        token.updated_at = _now()
        await db.commit()           # persiste o token rotacionado AGORA
        await db.refresh(token)     # recarrega o estado pós-commit

    return ContaAzulClient(token.access_token)


# ── Spec por entidade ───────────────────────────────────────────

@dataclass(frozen=True)
class EntitySpec:
    """Metadados de cada entidade Conta Azul."""
    name: str                         # 'pessoas', 'contas_receber', etc.
    model: type                       # classe SQLAlchemy do staging
    pk_field: str                     # campo PK no payload (sempre 'id')
    updated_at_field: str | None      # 'data_alteracao' | 'ultima_atualizacao' | None
    items_key: str                    # 'items' | 'itens' | '' (array puro)
    paginate: bool                    # True = usa limite/offset; False = chamada única


STATIC_ENTITIES: tuple[EntitySpec, ...] = (
    EntitySpec("pessoas",        StgCaPessoas,       "id", "data_alteracao",      "items", paginate=True),
    EntitySpec("produtos",       StgCaProdutos,      "id", "ultima_atualizacao",  "items", paginate=True),
    EntitySpec("servicos",       StgCaServicos,      "id", None,                  "itens", paginate=False),
    EntitySpec("vendedores",     StgCaVendedores,    "id", None,                  "",      paginate=False),
    EntitySpec("categorias",     StgCaCategorias,    "id", None,                  "itens", paginate=True),
    EntitySpec("centros_custo",  StgCaCentrosCusto,  "id", None,                  "itens", paginate=True),
    EntitySpec("categorias_dre", StgCaCategoriasDre, "id", None,                  "itens", paginate=False),
)


TRANSACTIONAL_ENTITIES: tuple[EntitySpec, ...] = (
    EntitySpec("contas_receber", StgCaContasReceber, "id", "data_alteracao", "itens", paginate=True),
    EntitySpec("contas_pagar",   StgCaContasPagar,   "id", "data_alteracao", "itens", paginate=True),
)


# Saldos bancários (Fase 1) — não usam o orquestrador genérico mas precisam
# estar no registry pra `_update_checkpoint` poder contar staging.
SALDOS_ENTITIES: tuple[EntitySpec, ...] = (
    EntitySpec("contas_financeiras", StgCaContasFinanceiras, "id", None, "itens", paginate=False),
    EntitySpec("saldos_atuais",      StgCaSaldosAtuais,      "id", None, "",      paginate=False),
    EntitySpec("saldos_iniciais",    StgCaSaldosIniciais,    "id", None, "itens", paginate=True),
)

# Detalhamento de parcelas (Onda 2) — não usa o orquestrador genérico
# (1 chamada por parcela em vez de paginação), mas precisa estar no registry
# pra `_update_checkpoint` poder contar staging.
DETAIL_ENTITIES: tuple[EntitySpec, ...] = (
    EntitySpec("parcelas_detalhe", StgCaParcelasDetalhe, "id", None, "", paginate=False),
)


_ALL_ENTITIES_BY_NAME: dict[str, EntitySpec] = {
    s.name: s for s in (
        *STATIC_ENTITIES, *TRANSACTIONAL_ENTITIES, *SALDOS_ENTITIES, *DETAIL_ENTITIES,
    )
}


def get_entity_spec(name: str) -> EntitySpec:
    if name not in _ALL_ENTITIES_BY_NAME:
        valid = ", ".join(_ALL_ENTITIES_BY_NAME.keys())
        raise ValueError(f"Entidade desconhecida '{name}'. Válidas: {valid}")
    return _ALL_ENTITIES_BY_NAME[name]


# ── Extração e upsert ───────────────────────────────────────────

def _extract_records(payload: Any, items_key: str) -> list[dict]:
    """Normaliza a resposta no formato esperado em lista de dicts."""
    if not items_key:
        # Array puro (vendedores)
        if isinstance(payload, list):
            return [r for r in payload if isinstance(r, dict)]
        return []
    if isinstance(payload, dict):
        inner = payload.get(items_key)
        if isinstance(inner, list):
            return [r for r in inner if isinstance(r, dict)]
    return []


async def _existing_external_ids(
    db: AsyncSession, model: type, tenant_id: str, external_ids: Iterable[str],
) -> set[str]:
    ids = list(external_ids)
    if not ids:
        return set()
    result = await db.execute(
        select(model.external_id).where(
            model.tenant_id == tenant_id,
            model.external_id.in_(ids),
        )
    )
    return {row[0] for row in result}


async def _upsert_records(
    db: AsyncSession, model: type, tenant_id: str, sync_job_id: int,
    records: list[dict], pk_field: str, updated_at_field: str | None,
) -> tuple[int, int, int]:
    """Upsert em massa. Retorna (records_fetched, inserted, updated)."""
    rows: list[dict] = []
    synced_at = _now()

    for raw in records:
        pk_value = raw.get(pk_field)
        if pk_value is None or pk_value == "":
            continue
        rows.append({
            "tenant_id": tenant_id,
            "external_id": str(pk_value),
            "external_updated_at": _parse_dt(raw.get(updated_at_field)) if updated_at_field else None,
            "raw_data": raw,
            "synced_at": synced_at,
            "sync_job_id": sync_job_id,
        })

    if not rows:
        return (len(records), 0, 0)

    existing = await _existing_external_ids(
        db, model, tenant_id, (r["external_id"] for r in rows)
    )

    # MySQL JSON tem limite por payload — fazer em batches de 500
    BATCH = 500
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        stmt = mysql_insert(model).values(chunk)
        stmt = stmt.on_duplicate_key_update(
            external_updated_at=stmt.inserted.external_updated_at,
            raw_data=stmt.inserted.raw_data,
            synced_at=stmt.inserted.synced_at,
            sync_job_id=stmt.inserted.sync_job_id,
        )
        await db.execute(stmt)

    inserted = sum(1 for r in rows if r["external_id"] not in existing)
    updated = len(rows) - inserted
    return (len(records), inserted, updated)


# ── Paginação ───────────────────────────────────────────────────

async def _paginate_static(
    client: ContaAzulClient, spec: EntitySpec,
    page_size: int = 500,
) -> list[dict]:
    """Paginadores das estáticas. Retorna lista achatada.

    Pagina via `pagina` (1-indexed) + `tamanho_pagina`. ATENÇÃO: o param
    `offset` é silenciosamente ignorado pela API — sempre devolve página 1.
    Aprendido via loop infinito de 237k chamadas duplicadas.
    """
    if not spec.paginate:
        # Servicos, vendedores, categorias_dre: chamada única
        if spec.name == "servicos":
            payload = await client.list_servicos()
        elif spec.name == "vendedores":
            payload = await client.list_vendedores()
        elif spec.name == "categorias_dre":
            payload = await client.list_categorias_dre()
        else:
            raise ValueError(f"Entidade '{spec.name}' não tem fetch sem paginação configurado.")
        return _extract_records(payload, spec.items_key)

    # Paginadas: pessoas, produtos, categorias, centros_custo
    method_map = {
        "pessoas": client.list_pessoas,
        "produtos": client.list_produtos,
        "categorias": client.list_categorias,
        "centros_custo": client.list_centros_custo,
    }
    method = method_map[spec.name]
    all_records: list[dict] = []
    pagina = 1
    while True:
        payload = await method(tamanho_pagina=page_size, pagina=pagina)
        records = _extract_records(payload, spec.items_key)
        all_records.extend(records)
        if len(records) < page_size:
            break
        pagina += 1
    return all_records


async def _paginate_transactional(
    client: ContaAzulClient, spec: EntitySpec,
    period_from: date, period_to: date,
    page_size: int = 500,
    data_alteracao_de: str | None = None,
    data_alteracao_ate: str | None = None,
) -> list[dict]:
    """Eventos financeiros (contas a receber/pagar) — paginados por
    `pagina` (1-indexed) + `tamanho_pagina`. `data_vencimento_de/ate` são
    OBRIGATÓRIOS pela API.

    Para delta sync: passe `data_alteracao_de/ate` + janela de vencimento
    ampla. A API filtra por intersecção, então só retorna o que foi alterado.
    """
    method_map = {
        "contas_receber": client.list_contas_receber,
        "contas_pagar": client.list_contas_pagar,
    }
    method = method_map[spec.name]
    all_records: list[dict] = []
    pagina = 1
    while True:
        payload = await method(
            data_vencimento_de=period_from,
            data_vencimento_ate=period_to,
            tamanho_pagina=page_size,
            pagina=pagina,
            data_alteracao_de=data_alteracao_de,
            data_alteracao_ate=data_alteracao_ate,
        )
        records = _extract_records(payload, spec.items_key)
        all_records.extend(records)
        if len(records) < page_size:
            break
        pagina += 1
    return all_records


# ── Lifecycle de SyncJob + Checkpoint (espelho do Clinicorp) ────

async def _start_job(
    db: AsyncSession, tenant_id: str, entity: str,
    period_from: date | None = None, period_to: date | None = None,
) -> SyncJob:
    job = SyncJob(
        tenant_id=tenant_id, source=SOURCE, entity=entity,
        status="running", period_from=period_from, period_to=period_to,
        started_at=_now(),
    )
    db.add(job)
    await db.flush()
    return job


async def _finish_job(
    db: AsyncSession, job: SyncJob,
    fetched: int, inserted: int, updated: int,
    errors_count: int = 0, error_message: str | None = None,
) -> None:
    finished = _now()
    job.finished_at = finished
    if job.started_at:
        job.duration_ms = int((finished - job.started_at).total_seconds() * 1000)
    job.records_fetched = fetched
    job.records_inserted = inserted
    job.records_updated = updated
    job.errors_count = errors_count
    job.error_message = error_message
    job.status = "error" if error_message else "success"


async def _count_staging_total(db: AsyncSession, tenant_id: str, model: type) -> int:
    result = await db.execute(
        select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
    )
    return int(result.scalar_one() or 0)


async def _update_checkpoint(
    db: AsyncSession, tenant_id: str, entity: str, job: SyncJob,
    period_from: date | None = None, period_to: date | None = None,
) -> None:
    spec = get_entity_spec(entity)
    total = await _count_staging_total(db, tenant_id, spec.model)
    cp = await db.get(SyncCheckpoint, (tenant_id, SOURCE, entity))
    if cp is None:
        cp = SyncCheckpoint(
            tenant_id=tenant_id, source=SOURCE, entity=entity,
            last_period_from=period_from, last_period_to=period_to,
            last_synced_at=_now(), last_sync_job_id=job.id,
            status=job.status, total_records=total,
        )
        db.add(cp)
    else:
        if period_from and (not cp.last_period_from or period_from > cp.last_period_from):
            cp.last_period_from = period_from
        if period_to and (not cp.last_period_to or period_to > cp.last_period_to):
            cp.last_period_to = period_to
        cp.last_synced_at = _now()
        cp.last_sync_job_id = job.id
        cp.status = job.status
        cp.total_records = total


# ── API pública: sync de UMA entidade estática ──────────────────

async def sync_static_entity(
    db: AsyncSession, tenant_id: str, spec: EntitySpec,
) -> SyncJob:
    job = await _start_job(db, tenant_id, spec.name)
    client: ContaAzulClient | None = None
    try:
        client = await _get_authenticated_client(db, tenant_id)
        records = await _paginate_static(client, spec)
        fetched, inserted, updated = await _upsert_records(
            db, spec.model, tenant_id, job.id, records, spec.pk_field, spec.updated_at_field,
        )
        await _finish_job(db, job, fetched, inserted, updated)
    except ContaAzulError as exc:
        await _finish_job(db, job, 0, 0, 0, errors_count=1, error_message=str(exc))
    except Exception as exc:  # noqa: BLE001
        await _finish_job(db, job, 0, 0, 0, errors_count=1, error_message=f"{type(exc).__name__}: {exc}")
    finally:
        if client is not None:
            await client.aclose()

    await _update_checkpoint(db, tenant_id, spec.name, job)
    await db.commit()
    await db.refresh(job)
    return job


async def sync_all_static(db: AsyncSession, tenant_id: str) -> list[SyncJob]:
    """Roda sync das 4 entidades estáticas em sequência."""
    jobs: list[SyncJob] = []
    for spec in STATIC_ENTITIES:
        jobs.append(await sync_static_entity(db, tenant_id, spec))
    return jobs


# ── API pública: sync de UMA entidade transacional num mês ──────

async def sync_transactional_entity(
    db: AsyncSession, tenant_id: str, spec: EntitySpec,
    year: int, month: int,
) -> SyncJob:
    from_date, to_date = _period_bounds_full_month(year, month)
    job = await _start_job(db, tenant_id, spec.name, period_from=from_date, period_to=to_date)
    client: ContaAzulClient | None = None
    try:
        client = await _get_authenticated_client(db, tenant_id)
        records = await _paginate_transactional(client, spec, from_date, to_date)
        fetched, inserted, updated = await _upsert_records(
            db, spec.model, tenant_id, job.id, records, spec.pk_field, spec.updated_at_field,
        )
        await _finish_job(db, job, fetched, inserted, updated)
    except ContaAzulError as exc:
        await _finish_job(db, job, 0, 0, 0, errors_count=1, error_message=str(exc))
    except Exception as exc:  # noqa: BLE001
        await _finish_job(db, job, 0, 0, 0, errors_count=1, error_message=f"{type(exc).__name__}: {exc}")
    finally:
        if client is not None:
            await client.aclose()

    await _update_checkpoint(db, tenant_id, spec.name, job, period_from=from_date, period_to=to_date)
    await db.commit()
    await db.refresh(job)
    return job


async def sync_transactional_batch(
    db: AsyncSession, tenant_id: str, year: int, month: int,
    entities: list[str] | None = None,
) -> list[SyncJob]:
    """Roda sync das entidades transacionais (todas ou as listadas) num mês."""
    if entities is None:
        specs = list(TRANSACTIONAL_ENTITIES)
    else:
        specs = [get_entity_spec(e) for e in entities]
        for s in specs:
            if s not in TRANSACTIONAL_ENTITIES:
                raise ValueError(f"Entidade '{s.name}' não é transacional.")
    jobs: list[SyncJob] = []
    for spec in specs:
        jobs.append(await sync_transactional_entity(db, tenant_id, spec, year, month))
    return jobs


# ── Delta sync — usa filtro `data_alteracao_de/ate` na busca normal ────

# Janela de vencimento ampla pra cobrir tudo independente de quando vence.
# A API exige data_vencimento obrigatória, mas com data_alteracao_de a
# intersecção retorna só o que mudou. Padrão V1 PHP: 2010 → +20 anos.
_DELTA_VENCIMENTO_DE = date(2010, 1, 1)
_DELTA_VENCIMENTO_ATE = date(2050, 12, 31)


async def sync_historical_contaazul(
    db: AsyncSession, tenant_id: str,
    *,
    year_start: int = 2020,
) -> list[SyncJob]:
    """Carga histórica COMPLETA de contas a receber/pagar do CA — pega TUDO
    desde `year_start` até hoje, em janelas mensais por `data_vencimento`.

    Diferente do sync mensal normal (que pega 1 mês de cada vez), este faz
    uma varredura completa pra cobrir parcelas pagas com vencimento em
    qualquer mês — necessário porque o `/buscar` não filtra por
    `data_pagamento`. Idempotente — pode rodar quantas vezes quiser.

    Usado no diagnóstico Onda 1: apenas R$ 92 de receita paga em abr/26
    aparece quando filtramos vencimento=abril, mas R$ 2.5M acumulados
    quando varremos todo o histórico.

    Custa ~12×N_anos chamadas (Parente histórico = ~72 chamadas, ~1min).
    """
    today = date.today()
    jobs: list[SyncJob] = []
    client: ContaAzulClient | None = None

    try:
        client = await _get_authenticated_client(db, tenant_id)
        for spec in TRANSACTIONAL_ENTITIES:
            # 1 SyncJob por entidade cobrindo a faixa toda
            period_from = date(year_start, 1, 1)
            period_to = date(today.year, 12, 31)
            job = await _start_job(
                db, tenant_id, spec.name,
                period_from=period_from, period_to=period_to,
            )
            try:
                # Itera ano-a-ano, mês-a-mês — janela CA aceita até 365d
                # mas mensal é mais granular (resilência a falhas)
                all_records: list[dict] = []
                y = year_start
                while y <= today.year:
                    last_month = today.month if y == today.year else 12
                    for m in range(1, last_month + 1):
                        from_d, to_d = _period_bounds_full_month(y, m)
                        records = await _paginate_transactional(
                            client, spec, from_d, to_d,
                        )
                        all_records.extend(records)
                    y += 1

                fetched, inserted, updated = await _upsert_records(
                    db, spec.model, tenant_id, job.id,
                    all_records, spec.pk_field, spec.updated_at_field,
                )
                await _finish_job(db, job, fetched, inserted, updated)
            except ContaAzulError as exc:
                await _finish_job(db, job, 0, 0, 0, errors_count=1, error_message=str(exc))
            except Exception as exc:  # noqa: BLE001
                await _finish_job(db, job, 0, 0, 0, errors_count=1, error_message=f"{type(exc).__name__}: {exc}")

            await _update_checkpoint(
                db, tenant_id, spec.name, job,
                period_from=period_from, period_to=period_to,
            )
            await db.commit()
            await db.refresh(job)
            jobs.append(job)
    finally:
        if client is not None:
            await client.aclose()

    return jobs


# ── Detalhamento de parcelas (Onda 2) ──────────────────────────

# Concorrência conservadora pro endpoint /parcelas/{id} — testado 2026-05-10:
# semaphore=3 + retry 429 dá vazão estável sem spike de erros.
_PARCELA_DETALHE_CONCURRENCY = 3


async def _fetch_parcela_detalhe_safe(
    client: ContaAzulClient,
    parcela_id: str,
    sem: asyncio.Semaphore,
) -> tuple[str, dict | None, str | None]:
    """Detalha 1 parcela com 1 retry no 429."""
    async with sem:
        for attempt in (1, 2):
            try:
                payload = await client.get_parcela_detalhe(parcela_id)
                return (parcela_id, payload, None)
            except ContaAzulError as exc:
                if attempt == 1 and "Rate limit" in str(exc):
                    await asyncio.sleep(3.0)
                    continue
                return (parcela_id, None, str(exc))
            except Exception as exc:  # noqa: BLE001
                return (parcela_id, None, f"{type(exc).__name__}: {exc}")
        return (parcela_id, None, "esgotou retries de rate limit")


async def sync_baixas_parcelas(
    db: AsyncSession,
    tenant_id: str,
    *,
    only_missing: bool = True,
    max_parcelas: int | None = None,
) -> SyncJob:
    """Sync detalhamento de parcelas pagas via /parcelas/{id}.

    Estratégia:
      1. Lista parcelas pagas (status ACQUITTED/PARTIAL) das stagings de
         contas_receber + contas_pagar
      2. Se `only_missing`, filtra as que ainda não têm detalhe em
         stg_ca_parcelas_detalhe (idempotência, retomada de carga)
      3. Detalha em paralelo com semaphore=3 + retry 429
      4. Salva raw_data em stg_ca_parcelas_detalhe (1 row por parcela)

    Custo: 1 chamada por parcela. Para Parente (~5500 pagas históricas),
    primeira carga ~30-40min. Subsequentes só processam novas.
    """
    job = await _start_job(db, tenant_id, "parcelas_detalhe")
    client: ContaAzulClient | None = None

    try:
        # 1. Lista parcelas pagas a detalhar — receber + pagar com ACQUITTED/PARTIAL
        q_pagas = await db.execute(text("""
            SELECT external_id FROM stg_ca_contas_receber
            WHERE tenant_id = :tid
              AND raw_data->>'$.status' IN ('ACQUITTED', 'PARTIAL')
            UNION
            SELECT external_id FROM stg_ca_contas_pagar
            WHERE tenant_id = :tid
              AND raw_data->>'$.status' IN ('ACQUITTED', 'PARTIAL')
        """), {"tid": tenant_id})
        pagas_ids = [row[0] for row in q_pagas.all()]

        # 2. Filtra missing
        if only_missing and pagas_ids:
            q_existing = await db.execute(text("""
                SELECT external_id FROM stg_ca_parcelas_detalhe
                WHERE tenant_id = :tid AND external_id IN :ids
            """).bindparams(bindparam("ids", expanding=True)),
                {"tid": tenant_id, "ids": pagas_ids})
            existing = {row[0] for row in q_existing.all()}
            to_fetch = [p for p in pagas_ids if p not in existing]
        else:
            to_fetch = pagas_ids

        if max_parcelas is not None:
            to_fetch = to_fetch[:max_parcelas]

        if not to_fetch:
            await _finish_job(db, job, 0, 0, 0)
            await _update_checkpoint(db, tenant_id, "parcelas_detalhe", job)
            await db.commit()
            await db.refresh(job)
            return job

        # 3. Detalha em paralelo
        client = await _get_authenticated_client(db, tenant_id)
        sem = asyncio.Semaphore(_PARCELA_DETALHE_CONCURRENCY)
        results = await asyncio.gather(*[
            _fetch_parcela_detalhe_safe(client, pid, sem) for pid in to_fetch
        ])

        # 4. Upsert raw em staging
        records: list[dict] = []
        errors: list[str] = []
        for pid, payload, err in results:
            if err is not None or payload is None:
                errors.append(f"{pid[:12]}…: {err}")
                continue
            payload["id"] = pid  # garantir pra _upsert_records
            records.append(payload)

        fetched, inserted, updated = await _upsert_records(
            db, StgCaParcelasDetalhe, tenant_id, job.id,
            records, "id", None,
        )
        await _finish_job(
            db, job, fetched, inserted, updated,
            errors_count=len(errors),
            error_message="; ".join(errors[:5]) if errors else None,
        )
    except ContaAzulError as exc:
        await _finish_job(db, job, 0, 0, 0, errors_count=1, error_message=str(exc))
    except Exception as exc:  # noqa: BLE001
        await _finish_job(db, job, 0, 0, 0, errors_count=1, error_message=f"{type(exc).__name__}: {exc}")
    finally:
        if client is not None:
            await client.aclose()

    await _update_checkpoint(db, tenant_id, "parcelas_detalhe", job)
    await db.commit()
    await db.refresh(job)
    return job


async def sync_alteracoes_recentes(
    db: AsyncSession, tenant_id: str, hours_back: int = 24,
) -> list[SyncJob]:
    """Delta sync: pega contas a receber/pagar alteradas nas últimas N horas.

    Estratégia: usa o filtro `data_alteracao_de/ate` da própria busca
    transacional (em vez de `/v1/financeiro/eventos-financeiros/alteracoes`,
    que retorna só IDs e exigiria N+1 chamadas). Apenas 2 chamadas:
    1× contas_receber + 1× contas_pagar. Schema idêntico ao sync mensal,
    upsert idempotente no mesmo staging.

    Útil pra manter staging atualizado durante o dia sem re-sincronizar
    meses completos. Economiza muita cota em produção.
    """
    if hours_back <= 0:
        raise ValueError(f"hours_back deve ser > 0, recebido {hours_back}")

    now = _now()
    since = now - timedelta(hours=hours_back)
    # Formato ISO local SP/GMT-3 (a API espera assim segundo a doc)
    alteracao_de = since.strftime("%Y-%m-%dT%H:%M:%S")
    alteracao_ate = now.strftime("%Y-%m-%dT%H:%M:%S")
    # Janela de vencimento serve só pra satisfazer o param obrigatório da API
    period_from = _DELTA_VENCIMENTO_DE
    period_to = _DELTA_VENCIMENTO_ATE

    jobs: list[SyncJob] = []
    for spec in TRANSACTIONAL_ENTITIES:
        # period_from/to do SyncJob = janela de vencimento (mantém schema),
        # janela de alteração fica registrada via _now() em started_at e a
        # janela passada nos params da API.
        job = await _start_job(db, tenant_id, spec.name, period_from=period_from, period_to=period_to)
        client: ContaAzulClient | None = None
        try:
            client = await _get_authenticated_client(db, tenant_id)
            records = await _paginate_transactional(
                client, spec, period_from, period_to,
                data_alteracao_de=alteracao_de,
                data_alteracao_ate=alteracao_ate,
            )
            fetched, inserted, updated = await _upsert_records(
                db, spec.model, tenant_id, job.id, records, spec.pk_field, spec.updated_at_field,
            )
            await _finish_job(db, job, fetched, inserted, updated)
        except ContaAzulError as exc:
            await _finish_job(db, job, 0, 0, 0, errors_count=1, error_message=str(exc))
        except Exception as exc:  # noqa: BLE001
            await _finish_job(db, job, 0, 0, 0, errors_count=1, error_message=f"{type(exc).__name__}: {exc}")
        finally:
            if client is not None:
                await client.aclose()
        # Não atualiza checkpoint — delta sync não representa "estado final
        # do mês". O total no checkpoint continua refletindo o último sync
        # full daquela entidade.
        await db.commit()
        await db.refresh(job)
        jobs.append(job)
    return jobs


# ── Saldos bancários (Fase 1 Show no Financeiro) ──────────────────

# Concorrência conservadora: ~10-36 contas × ~200ms cada.
# Semaphore=4 já paraleliza bem (~1s) sem disparar rate limit do CA
# (com 8 deu 429 em 1 de 10 contas no smoke 2026-05-09).
_SALDO_ATUAL_CONCURRENCY = 4


async def _fetch_saldo_atual_safe(
    client: ContaAzulClient,
    conta_id: str,
    sem: asyncio.Semaphore,
) -> tuple[str, dict | None, str | None]:
    """Pega o saldo de UMA conta com 1 retry no 429 (rate limit).

    Retorna (conta_id, payload, erro_msg).
    """
    async with sem:
        for attempt in (1, 2):
            try:
                payload = await client.get_saldo_atual(conta_id)
                return (conta_id, payload, None)
            except ContaAzulError as exc:
                if attempt == 1 and "Rate limit" in str(exc):
                    await asyncio.sleep(3.0)
                    continue
                return (conta_id, None, str(exc))
            except Exception as exc:  # noqa: BLE001
                return (conta_id, None, f"{type(exc).__name__}: {exc}")
        return (conta_id, None, "esgotou retries de rate limit")


async def sync_saldos_bancarios(
    db: AsyncSession,
    tenant_id: str,
    *,
    saldos_iniciais_meses: int = 12,
) -> list[SyncJob]:
    """Sincroniza contas financeiras + saldos atuais + saldos iniciais.

    3 jobs encadeados:
      1. contas_financeiras (1 chamada)
      2. saldos_atuais (N chamadas paralelas, 1 por conta — asyncio.gather)
      3. saldos_iniciais (1 chamada por mês de janela, default últimos 12m)

    Os 3 jobs ficam em sync_jobs com entity próprio pra rastreio.
    """
    jobs: list[SyncJob] = []
    client: ContaAzulClient | None = None
    try:
        client = await _get_authenticated_client(db, tenant_id)

        # ── 1. contas_financeiras ────────────────────────────────
        job1 = await _start_job(db, tenant_id, "contas_financeiras")
        try:
            payload = await client.list_contas_financeiras()
            records = _extract_records(payload, "itens")
            fetched, inserted, updated = await _upsert_records(
                db, StgCaContasFinanceiras, tenant_id, job1.id,
                records, "id", None,
            )
            await _finish_job(db, job1, fetched, inserted, updated)
        except ContaAzulError as exc:
            await _finish_job(db, job1, 0, 0, 0, errors_count=1, error_message=str(exc))
            await _update_checkpoint(db, tenant_id, "contas_financeiras", job1)  # type: ignore[arg-type]
            await db.commit()
            jobs.append(job1)
            return jobs
        await _update_checkpoint(db, tenant_id, "contas_financeiras", job1)
        await db.commit()
        await db.refresh(job1)
        jobs.append(job1)

        # IDs das contas pra puxar saldo atual em paralelo
        conta_ids = [str(r["id"]) for r in records if r.get("id")]

        # ── 2. saldos_atuais (paralelo) ──────────────────────────
        job2 = await _start_job(db, tenant_id, "saldos_atuais")
        try:
            sem = asyncio.Semaphore(_SALDO_ATUAL_CONCURRENCY)
            results = await asyncio.gather(*[
                _fetch_saldo_atual_safe(client, cid, sem) for cid in conta_ids
            ])
            now_iso = _now()
            saldo_records: list[dict] = []
            errors: list[str] = []
            for cid, payload, err in results:
                if err is not None or payload is None:
                    errors.append(f"{cid}: {err}")
                    continue
                # Inflar payload com conta_id pra rastrear na promo
                saldo_records.append({
                    "id": cid,
                    "id_conta_financeira": cid,
                    "saldo_atual": payload.get("saldo_atual"),
                    "consultado_em": now_iso.isoformat(),
                })
            fetched, inserted, updated = await _upsert_records(
                db, StgCaSaldosAtuais, tenant_id, job2.id,
                saldo_records, "id", None,
            )
            await _finish_job(
                db, job2, fetched, inserted, updated,
                errors_count=len(errors),
                error_message="; ".join(errors[:5]) if errors else None,
            )
        except ContaAzulError as exc:
            await _finish_job(db, job2, 0, 0, 0, errors_count=1, error_message=str(exc))
        except Exception as exc:  # noqa: BLE001
            await _finish_job(db, job2, 0, 0, 0, errors_count=1, error_message=f"{type(exc).__name__}: {exc}")
        await _update_checkpoint(db, tenant_id, "saldos_atuais", job2)
        await db.commit()
        await db.refresh(job2)
        jobs.append(job2)

        # ── 3. saldos_iniciais ───────────────────────────────────
        # API CA limita a janela em 365 dias por chamada — então fazemos
        # uma chamada POR MÊS dos últimos N meses. Datetime SEM Z (pegadinha
        # CA confirmada 2026-05-09).
        today = date.today()
        # Lista de (year, month) dos últimos N meses, mais recente primeiro
        meses: list[tuple[int, int]] = []
        y, m = today.year, today.month
        for _ in range(saldos_iniciais_meses):
            meses.append((y, m))
            y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        meses.reverse()
        period_from = date(meses[0][0], meses[0][1], 1)
        ult_y, ult_m = meses[-1]
        period_to = date(ult_y + 1, 1, 1) if ult_m == 12 else date(ult_y, ult_m + 1, 1)

        job3 = await _start_job(
            db, tenant_id, "saldos_iniciais",
            period_from=period_from, period_to=period_to,
        )
        try:
            all_records: list[dict] = []
            for yy, mm in meses:
                mes_inicio = date(yy, mm, 1)
                mes_fim = date(yy + 1, 1, 1) if mm == 12 else date(yy, mm + 1, 1)
                data_inicio = f"{mes_inicio.isoformat()}T00:00:00"
                data_fim = f"{mes_fim.isoformat()}T00:00:00"
                pagina = 1
                page_size = 500
                while True:
                    payload_si = await client.list_saldos_iniciais(
                        data_inicio=data_inicio, data_fim=data_fim,
                        tamanho_pagina=page_size, pagina=pagina,
                    )
                    page_records = _extract_records(payload_si, "itens")
                    all_records.extend(page_records)
                    if len(page_records) < page_size:
                        break
                    pagina += 1

            # external_id artificial (chave composta)
            for r in all_records:
                conta = r.get("id_conta_financeira") or ""
                tipo = r.get("tipo") or ""
                dc = r.get("data_competencia") or ""
                # Trunca em 160 (limite do schema). Componentes são curtos.
                r["id"] = f"{conta}|{tipo}|{dc}"[:160]

            fetched, inserted, updated = await _upsert_records(
                db, StgCaSaldosIniciais, tenant_id, job3.id,
                all_records, "id", None,
            )
            await _finish_job(db, job3, fetched, inserted, updated)
        except ContaAzulError as exc:
            await _finish_job(db, job3, 0, 0, 0, errors_count=1, error_message=str(exc))
        except Exception as exc:  # noqa: BLE001
            await _finish_job(db, job3, 0, 0, 0, errors_count=1, error_message=f"{type(exc).__name__}: {exc}")
        await _update_checkpoint(
            db, tenant_id, "saldos_iniciais", job3,
            period_from=period_from, period_to=period_to,
        )
        await db.commit()
        await db.refresh(job3)
        jobs.append(job3)
    finally:
        if client is not None:
            await client.aclose()

    return jobs
