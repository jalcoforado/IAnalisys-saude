from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class SyncJobResponse(BaseModel):
    id: int
    tenant_id: str
    source: str
    entity: str
    status: str
    period_from: Optional[date] = None
    period_to: Optional[date] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    records_fetched: Optional[int] = None
    records_inserted: Optional[int] = None
    records_updated: Optional[int] = None
    errors_count: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class StaticSyncResponse(BaseModel):
    """Resposta de POST /sync/clinicorp/static — agrega o resultado das 8 entidades."""
    jobs: list[SyncJobResponse]
    total_inserted: int
    total_updated: int
    total_errors: int


class TransactionalSyncRequest(BaseModel):
    """Request para sync de UMA entidade transacional num mês."""
    entity: str = Field(..., description="Nome da entidade: appointments, estimates, payments, invoices, receipts, summary_entries")
    year: int = Field(..., ge=2019, le=2100)
    month: int = Field(..., ge=1, le=12)


class TransactionalBatchRequest(BaseModel):
    """Request para sync de várias entidades transacionais num único mês."""
    year: int = Field(..., ge=2019, le=2100)
    month: int = Field(..., ge=1, le=12)
    entities: Optional[list[str]] = Field(
        None,
        description="Se omitido, roda todas as 6 entidades transacionais.",
    )


class TransactionalSyncResponse(BaseModel):
    jobs: list[SyncJobResponse]
    total_inserted: int
    total_updated: int
    total_errors: int


class KpisMonthlyRequest(BaseModel):
    """Request para sync dos KPIs mensais agregados num mês."""
    year: int = Field(..., ge=2019, le=2100)
    month: int = Field(..., ge=1, le=12)


class DeltaSyncRequest(BaseModel):
    """Request para delta sync — janela de horas atrás até agora.

    Usado pelo CA pra atualizar staging com alterações recentes sem
    re-sincronizar mês completo. Padrão 24h, máximo 720h (30 dias).
    """
    hours_back: int = Field(24, ge=1, le=720)


class FullSyncResponse(BaseModel):
    """Resposta do orquestrador POST /sync/contaazul/full.

    Agrega resultados de: estáticos, saldos bancários, transacional do mês,
    transferências do mês, detalhar baixas, rebuild CORE+ANALYTICS.
    """
    jobs: list[SyncJobResponse]
    total_inserted: int
    total_updated: int
    total_errors: int
    duration_ms: int
    rebuild_done: bool


class CheckpointResponse(BaseModel):
    tenant_id: str
    source: str
    entity: str
    last_period_from: Optional[date] = None
    last_period_to: Optional[date] = None
    last_synced_at: Optional[datetime] = None
    last_sync_job_id: Optional[int] = None
    status: str
    total_records: int

    model_config = {"from_attributes": True}
