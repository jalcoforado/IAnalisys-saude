"""
Serviço de sincronização Clinicorp → staging (record-level, idempotente).

Padrão por entidade:
  1. Cria sync_jobs com status='running'
  2. Chama o endpoint da Clinicorp via ClinicorpClient
  3. Para cada registro, faz INSERT ... ON DUPLICATE KEY UPDATE em stg_cc_<entity>
  4. Atualiza sync_jobs (status, métricas, duração)
  5. Atualiza sync_checkpoints com a contagem real em staging

Idempotência: chave única (tenant_id, external_id). Re-rodar nunca duplica.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.clinicorp.client import ClinicorpClient, ClinicorpError
from app.models.staging import (
    StgCcAppointmentCategories,
    StgCcAppointments,
    StgCcAppointmentStatuses,
    StgCcBusiness,
    StgCcCrmCampaigns,
    StgCcEstimates,
    StgCcInvoices,
    StgCcKpisMonthly,
    StgCcPayments,
    StgCcProcedures,
    StgCcProfessionals,
    StgCcReceipts,
    StgCcSpecialties,
    StgCcSummaryEntries,
    StgCcUsers,
)
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_job import SyncJob

SOURCE = "clinicorp"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_dt(value: Any) -> datetime | None:
    """Aceita ISO-8601 ou retorna None se valor for vazio/inválido."""
    if not value or not isinstance(value, str):
        return None
    try:
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except (ValueError, TypeError):
        return None


def _period_bounds(
    year: int, month: int, today: date | None = None, allows_future: bool = False,
) -> tuple[date, date]:
    """
    Calcula (from_date, to_date) cobrindo o mês.

    Por default `to_date` é capado em hoje — protege entidades transacionais
    como payments/invoices de buscar datas sem sentido. Quando `allows_future`
    é True (caso de appointments — gestor precisa ver o futuro agendado),
    mantém o último dia do mês.

    Levanta ValueError se o mês ainda não começou.
    """
    if not (1 <= month <= 12):
        raise ValueError(f"Mês inválido: {month}")
    from_date = date(year, month, 1)
    if month == 12:
        to_date = date(year, 12, 31)
    else:
        to_date = date(year, month + 1, 1) - timedelta(days=1)
    today = today or date.today()
    if from_date > today:
        raise ValueError(f"Período {year}-{month:02d} ainda não começou.")
    if to_date > today and not allows_future:
        to_date = today
    return from_date, to_date


@dataclass(frozen=True)
class EntitySpec:
    """Metadados de cada entidade Clinicorp (estática ou transacional)."""
    name: str                     # 'business', 'appointments', etc.
    model: type                   # classe SQLAlchemy do staging
    client_method: str            # método em ClinicorpClient
    pk_field: str                 # campo PK no payload
    updated_at_field: str | None  # campo de timestamp de mudança, se houver
    allows_future: bool = False   # True pra appointments — sincroniza datas futuras
                                  # do mês. Default False protege payments/invoices/etc
                                  # de retornar dados sem sentido (não há pagamento
                                  # futuro).


# ── Configuração das 8 entidades estáticas ──────────────────────
STATIC_ENTITIES: tuple[EntitySpec, ...] = (
    EntitySpec("business",               StgCcBusiness,              "list_business",                "id",   None),
    EntitySpec("users",                  StgCcUsers,                 "list_users",                   "id",   None),
    EntitySpec("professionals",          StgCcProfessionals,         "list_professionals",           "id",   None),
    EntitySpec("specialties",            StgCcSpecialties,           "list_specialties",             "id",   "z_LastChange_Date"),
    EntitySpec("procedures",             StgCcProcedures,            "list_procedures",              "id",   None),
    EntitySpec("appointment_categories", StgCcAppointmentCategories, "list_appointment_categories",  "id",   None),
    EntitySpec("appointment_statuses",   StgCcAppointmentStatuses,   "list_appointment_statuses",    "id",   "z_LastChange_Date"),
    EntitySpec("crm_campaigns",          StgCcCrmCampaigns,          "list_active_campaigns",        "Name", None),
)


# ── Configuração das 6 entidades transacionais (por mês) ────────
TRANSACTIONAL_ENTITIES: tuple[EntitySpec, ...] = (
    EntitySpec("appointments",    StgCcAppointments,    "list_appointments",  "id",          "ModifiedDate", allows_future=True),
    EntitySpec("estimates",       StgCcEstimates,       "list_estimates",     "TreatmentId", "LastChange_Date"),
    EntitySpec("payments",        StgCcPayments,        "list_payments",      "id",          "z_LastChange_Date"),
    EntitySpec("invoices",        StgCcInvoices,        "list_invoices",      "InvoiceId",   None),
    EntitySpec("receipts",        StgCcReceipts,        "list_receipts",      "id",          None),
    EntitySpec("summary_entries", StgCcSummaryEntries,  "list_summary",       "id",          None),
)


# ── Configuração das entidades agregadas ────────────────────────
# kpis_monthly não tem client_method único (chama 10 endpoints) nem PK numérico
# (PK = 'YYYY-MM-01'). Entrada aqui serve apenas para o lookup de modelo no checkpoint.
AGGREGATED_ENTITIES: tuple[EntitySpec, ...] = (
    EntitySpec("kpis_monthly", StgCcKpisMonthly, "", "external_id", None),
)


# Lookup name → spec, para resolver entidades vindas da API
_ALL_ENTITIES_BY_NAME: dict[str, EntitySpec] = {
    s.name: s for s in (*STATIC_ENTITIES, *TRANSACTIONAL_ENTITIES, *AGGREGATED_ENTITIES)
}


def get_entity_spec(name: str) -> EntitySpec:
    if name not in _ALL_ENTITIES_BY_NAME:
        valid = ", ".join(_ALL_ENTITIES_BY_NAME.keys())
        raise ValueError(f"Entidade desconhecida '{name}'. Válidas: {valid}")
    return _ALL_ENTITIES_BY_NAME[name]


# ── Helpers de upsert genérico ──────────────────────────────────

def _extract_records(payload: Any) -> list[dict]:
    """
    Normaliza o retorno da Clinicorp em uma lista de dicts.

    Formatos suportados:
    - [..] direto
    - {'values'|'list'|'data'|'results': [..]}
    - {grupo1: [..], grupo2: [..]}  (ex: /procedures/list agrupado por PriceListName)
    - {} agregado de 1 linha (vira [{...}])
    """
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("values", "list", "data", "results"):
            inner = payload.get(key)
            if isinstance(inner, list):
                return [r for r in inner if isinstance(r, dict)]
        # Dict agrupado: todos os values são listas → achata
        if payload and all(isinstance(v, list) for v in payload.values()):
            return [r for lst in payload.values() for r in lst if isinstance(r, dict)]
        # Caso "1 linha agregada"
        return [payload]
    return []


async def _existing_external_ids(
    db: AsyncSession, model: type, tenant_id: str, external_ids: Iterable[str],
) -> set[str]:
    """Set de external_id já presentes em staging (para contar inserted vs updated)."""
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
    """
    Upsert em massa. Retorna (records_fetched, inserted, updated).
    Registros sem PK são ignorados silenciosamente.
    """
    rows: list[dict] = []
    skipped_no_pk = 0
    synced_at = _now()

    for raw in records:
        pk_value = raw.get(pk_field)
        if pk_value is None or pk_value == "":
            skipped_no_pk += 1
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

    stmt = mysql_insert(model).values(rows)
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


# ── Lifecycle de SyncJob + Checkpoint ───────────────────────────

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
    await db.flush()  # garante job.id
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
    """Conta registros atuais em staging (fonte de verdade pro checkpoint)."""
    result = await db.execute(
        select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
    )
    return int(result.scalar_one() or 0)


async def _update_checkpoint(
    db: AsyncSession, tenant_id: str, entity: str, job: SyncJob,
    period_from: date | None = None, period_to: date | None = None,
) -> None:
    """Upsert de sync_checkpoints com a contagem real em staging."""
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
        # Para transacionais, mantém o "último" como o mais recente em datas
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
    """Sincroniza uma entidade estática. Retorna o SyncJob finalizado."""
    job = await _start_job(db, tenant_id, spec.name)

    client = ClinicorpClient()
    try:
        method = getattr(client, spec.client_method)
        payload = await method()
        records = _extract_records(payload)
        fetched, inserted, updated = await _upsert_records(
            db, spec.model, tenant_id, job.id, records, spec.pk_field, spec.updated_at_field,
        )
        await _finish_job(db, job, fetched, inserted, updated)
    except ClinicorpError as exc:
        await _finish_job(db, job, 0, 0, 0, errors_count=1, error_message=str(exc))
    except Exception as exc:
        await _finish_job(db, job, 0, 0, 0, errors_count=1, error_message=f"{type(exc).__name__}: {exc}")

    await _update_checkpoint(db, tenant_id, spec.name, job)
    await db.commit()
    await db.refresh(job)
    return job


async def sync_all_static(db: AsyncSession, tenant_id: str) -> list[SyncJob]:
    """Roda sync das 8 entidades estáticas em sequência."""
    jobs: list[SyncJob] = []
    for spec in STATIC_ENTITIES:
        jobs.append(await sync_static_entity(db, tenant_id, spec))
    return jobs


# ── API pública: sync de UMA entidade transacional num mês ──────

async def sync_transactional_entity(
    db: AsyncSession, tenant_id: str, spec: EntitySpec,
    year: int, month: int,
) -> SyncJob:
    """Sincroniza uma entidade transacional cobrindo o mês indicado."""
    from_date, to_date = _period_bounds(year, month, allows_future=spec.allows_future)
    job = await _start_job(db, tenant_id, spec.name, period_from=from_date, period_to=to_date)

    client = ClinicorpClient()
    try:
        method = getattr(client, spec.client_method)
        payload = await method(from_date.isoformat(), to_date.isoformat())
        records = _extract_records(payload)
        fetched, inserted, updated = await _upsert_records(
            db, spec.model, tenant_id, job.id, records, spec.pk_field, spec.updated_at_field,
        )
        await _finish_job(db, job, fetched, inserted, updated)
    except ClinicorpError as exc:
        await _finish_job(db, job, 0, 0, 0, errors_count=1, error_message=str(exc))
    except Exception as exc:
        await _finish_job(db, job, 0, 0, 0, errors_count=1, error_message=f"{type(exc).__name__}: {exc}")

    await _update_checkpoint(db, tenant_id, spec.name, job, period_from=from_date, period_to=to_date)
    await db.commit()
    await db.refresh(job)
    return job


async def sync_transactional_batch(
    db: AsyncSession, tenant_id: str, year: int, month: int,
    entities: list[str] | None = None,
) -> list[SyncJob]:
    """
    Roda sync das entidades transacionais (todas ou as listadas) num mês.
    Falha numa não interrompe as outras.
    """
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


# ── KPIs mensais agregados ──────────────────────────────────────
# 10 endpoints chamados em paralelo via asyncio.gather, gravados como
# 1 linha por mês em stg_cc_kpis_monthly com external_id='YYYY-MM-01'.
#
# Alimentam dashboards executivos rápidos sem recalcular dos eventos.
# Os values[] de financial/list_summary NÃO entram aqui (já estão em
# stg_cc_summary_entries) — guardamos só os agregados.

KPI_ENDPOINTS = (
    "cash_flow",
    "payments_aggregated",
    "financial_summary",
    "average_installments",
    "appointment_info",
    "estimates_conversion",
    "expertise_revenue",
    "patient_estimates",
    "misses_goals",
    "sales_goals",
)


async def _fetch_kpi_payloads(
    client: ClinicorpClient, from_date: str, to_date: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    """
    Chama os 10 endpoints em paralelo. Retorna (payloads_ok, errors).
    Falhas isoladas viram entradas no dict errors em vez de derrubar tudo.
    """
    methods = {
        "cash_flow":            client.list_cash_flow,
        "payments_aggregated":  client.list_payments_aggregated,
        "financial_summary":    client.list_summary,
        "average_installments": client.average_installments,
        "appointment_info":     client.list_appointment_info,
        "estimates_conversion": client.list_estimates_conversion,
        "expertise_revenue":    client.list_expertise_revenue,
        "patient_estimates":    client.list_patient_estimates,
        "misses_goals":         client.list_misses_goals,
        "sales_goals":          client.list_sales_goals,
    }
    keys = list(methods.keys())
    results = await asyncio.gather(
        *(m(from_date, to_date) for m in methods.values()),
        return_exceptions=True,
    )
    payloads: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for key, res in zip(keys, results):
        if isinstance(res, Exception):
            errors[key] = f"{type(res).__name__}: {res}"
        else:
            payloads[key] = res
    return payloads, errors


def _strip_summary_values(payload: Any) -> Any:
    """list_summary retorna {From, To, ..., values[..]} — descartamos values[] aqui (já capturado em summary_entries)."""
    if isinstance(payload, dict) and "values" in payload:
        return {k: v for k, v in payload.items() if k != "values"}
    return payload


async def sync_kpis_monthly(
    db: AsyncSession, tenant_id: str, year: int, month: int,
) -> SyncJob:
    """
    Sincroniza os KPIs mensais agregados num único job.
    Grava 1 linha em stg_cc_kpis_monthly com external_id='YYYY-MM-01'.
    """
    from_date, to_date = _period_bounds(year, month)
    period_id = from_date.isoformat()  # 'YYYY-MM-01'
    job = await _start_job(
        db, tenant_id, "kpis_monthly",
        period_from=from_date, period_to=to_date,
    )

    client = ClinicorpClient()
    try:
        payloads, errors = await _fetch_kpi_payloads(
            client, from_date.isoformat(), to_date.isoformat(),
        )
        if "financial_summary" in payloads:
            payloads["financial_summary"] = _strip_summary_values(payloads["financial_summary"])

        # raw_data: dict com os 10 payloads (e erros, se houver)
        raw_data = {
            "period_from": from_date.isoformat(),
            "period_to": to_date.isoformat(),
            "endpoints_ok": list(payloads.keys()),
            "endpoints_failed": list(errors.keys()),
            "errors": errors,
            "data": payloads,
        }

        existing = await _existing_external_ids(
            db, StgCcKpisMonthly, tenant_id, [period_id],
        )
        is_update = period_id in existing

        stmt = mysql_insert(StgCcKpisMonthly).values([{
            "tenant_id": tenant_id,
            "external_id": period_id,
            "external_updated_at": _now(),
            "raw_data": raw_data,
            "synced_at": _now(),
            "sync_job_id": job.id,
        }])
        stmt = stmt.on_duplicate_key_update(
            external_updated_at=stmt.inserted.external_updated_at,
            raw_data=stmt.inserted.raw_data,
            synced_at=stmt.inserted.synced_at,
            sync_job_id=stmt.inserted.sync_job_id,
        )
        await db.execute(stmt)

        await _finish_job(
            db, job,
            fetched=len(payloads) + len(errors),
            inserted=0 if is_update else 1,
            updated=1 if is_update else 0,
            errors_count=len(errors),
            error_message=None if not errors else f"{len(errors)} endpoints falharam: {', '.join(errors.keys())}",
        )
    except ClinicorpError as exc:
        await _finish_job(db, job, 0, 0, 0, errors_count=1, error_message=str(exc))
    except Exception as exc:
        await _finish_job(db, job, 0, 0, 0, errors_count=1, error_message=f"{type(exc).__name__}: {exc}")

    await _update_checkpoint(
        db, tenant_id, "kpis_monthly", job,
        period_from=from_date, period_to=to_date,
    )
    await db.commit()
    await db.refresh(job)
    return job
