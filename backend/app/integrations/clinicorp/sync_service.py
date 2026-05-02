"""
Serviço de sincronização Clinicorp → staging.

Fluxo:
  1. Cria registro em sync_jobs com status=running
  2. Chama os endpoints da Clinicorp (via ClinicorpClient)
  3. Grava raw_data nas tabelas stg_*
  4. Atualiza sync_job com status=success (ou error)

Cada tabela de staging recebe uma linha por execução de sync,
contendo o JSON bruto retornado pela API para o período solicitado.
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.clinicorp.client import ClinicorpClient, ClinicorpError
from app.models.staging import (
    StgAnalytics,
    StgAppointment,
    StgCashFlow,
    StgEstimate,
    StgEstimatesConversion,
    StgFinancialSummary,
    StgPayment,
)
from app.models.sync_job import SyncJob


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def run_clinicorp_sync(
    db: AsyncSession,
    tenant_id: str,
    from_date: str,
    to_date: str,
) -> SyncJob:
    """
    Executa o sync completo para um tenant no período indicado.
    Retorna o SyncJob atualizado ao final.
    """
    job = SyncJob(
        tenant_id=tenant_id,
        source="clinicorp",
        status="running",
        ref_date_from=from_date,
        ref_date_to=to_date,
        started_at=_now(),
    )
    db.add(job)
    await db.flush()  # garante que job.id existe antes de continuar

    client = ClinicorpClient()
    records = 0

    try:
        # ── Coleta em paralelo seria ideal, mas mantemos sequencial
        # para não sobrecarregar a API da Clinicorp.
        results = await _fetch_all(client, from_date, to_date)

        # ── Grava staging ────────────────────────────────────
        synced_at = _now()

        db.add(StgAppointment(
            tenant_id=tenant_id,
            ref_date_from=from_date,
            ref_date_to=to_date,
            raw_data=results["appointments"],
            synced_at=synced_at,
        ))
        db.add(StgEstimate(
            tenant_id=tenant_id,
            ref_date_from=from_date,
            ref_date_to=to_date,
            raw_data=results["estimates"],
            synced_at=synced_at,
        ))
        db.add(StgCashFlow(
            tenant_id=tenant_id,
            ref_date_from=from_date,
            ref_date_to=to_date,
            raw_data=results["cash_flow"],
            synced_at=synced_at,
        ))
        db.add(StgPayment(
            tenant_id=tenant_id,
            ref_date_from=from_date,
            ref_date_to=to_date,
            raw_data=results["payments"],
            synced_at=synced_at,
        ))
        db.add(StgAnalytics(
            tenant_id=tenant_id,
            ref_date_from=from_date,
            ref_date_to=to_date,
            raw_data=results["analytics"],
            synced_at=synced_at,
        ))
        db.add(StgFinancialSummary(
            tenant_id=tenant_id,
            ref_date_from=from_date,
            ref_date_to=to_date,
            raw_data=results["financial_summary"],
            synced_at=synced_at,
        ))
        db.add(StgEstimatesConversion(
            tenant_id=tenant_id,
            ref_date_from=from_date,
            ref_date_to=to_date,
            raw_data=results["estimates_conversion"],
            synced_at=synced_at,
        ))

        # Conta itens recebidos (soma dos arrays/dicts de cada endpoint)
        records = sum(_count_records(v) for v in results.values())

        job.status = "success"
        job.records_fetched = records
        job.finished_at = _now()

    except (ClinicorpError, Exception) as exc:
        job.status = "error"
        job.error_message = str(exc)
        job.finished_at = _now()

    await db.commit()
    await db.refresh(job)
    return job


async def _fetch_all(client: ClinicorpClient, from_date: str, to_date: str) -> dict[str, Any]:
    """Busca todos os endpoints necessários para o staging."""
    return {
        "appointments": await client.get_appointments(from_date, to_date),
        "estimates": await client.get_estimates(from_date, to_date),
        "cash_flow": await client.get_cash_flow(from_date, to_date),
        "payments": await client.get_payments(from_date, to_date),
        "analytics": await client.get_analytics(from_date, to_date),
        "financial_summary": await client.get_financial_summary(from_date, to_date),
        "estimates_conversion": await client.get_estimates_conversion(from_date, to_date),
    }


def _count_records(data: Any) -> int:
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        # Clinicorp às vezes retorna {"data": [...]}
        for key in ("data", "results", "items"):
            if isinstance(data.get(key), list):
                return len(data[key])
        return 1
    return 0
