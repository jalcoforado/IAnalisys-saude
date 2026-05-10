"""
Endpoints de sincronização Clinicorp.

POST /sync/clinicorp/static                   — 8 entidades estáticas
POST /sync/clinicorp/transactional            — 1 entidade transacional / 1 mês
POST /sync/clinicorp/transactional/batch      — N entidades transacionais / 1 mês
POST /sync/clinicorp/kpis_monthly             — 10 endpoints agregados / 1 mês
GET  /sync/jobs                               — lista jobs de sync recentes
GET  /sync/checkpoints                        — estado por entidade
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.permissions import requires
from app.db.session import AsyncSessionLocal, get_db
from app.integrations.clinicorp.patients_sync import sync_patients_details
from app.integrations.clinicorp.sync_service import (
    get_entity_spec,
    sync_all_static,
    sync_kpis_monthly,
    sync_transactional_batch,
    sync_transactional_entity,
    TRANSACTIONAL_ENTITIES,
)
from app.integrations.contaazul import sync_service as ca_sync
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.sync_job import SyncJob
from app.schemas.auth import UserMe
from app.schemas.sync import (
    CheckpointResponse,
    DeltaSyncRequest,
    KpisMonthlyRequest,
    StaticSyncResponse,
    SyncJobResponse,
    TransactionalBatchRequest,
    TransactionalSyncRequest,
    TransactionalSyncResponse,
)

router = APIRouter(prefix="/sync", tags=["sync"])


def _require_tenant(user: UserMe) -> str:
    if not user.tenant_id:
        raise HTTPException(status_code=400, detail="Usuário sem tenant associado.")
    return user.tenant_id


@router.post("/clinicorp/static", response_model=StaticSyncResponse, status_code=200)
async def sync_clinicorp_static(
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> StaticSyncResponse:
    """
    Dispara sync das 8 entidades estáticas Clinicorp.
    Cada entidade gera um SyncJob independente. Falhas isoladas
    não interrompem as demais.
    """
    tenant_id = _require_tenant(current_user)
    jobs = await sync_all_static(db, tenant_id)
    return StaticSyncResponse(
        jobs=[SyncJobResponse.model_validate(j) for j in jobs],
        total_inserted=sum(j.records_inserted or 0 for j in jobs),
        total_updated=sum(j.records_updated or 0 for j in jobs),
        total_errors=sum(j.errors_count or 0 for j in jobs),
    )


_log = logging.getLogger(__name__)


async def _run_patients_details_in_background(tenant_id: str, job_id: int) -> None:
    """Executa sync de patients/details em sessão DB própria.
    Roda fora do request — sobrevive a timeout/disconnect do cliente HTTP.
    Em caso de exceção não tratada, marca o job como error.
    """
    async with AsyncSessionLocal() as session:
        try:
            await sync_patients_details(session, tenant_id, existing_job_id=job_id)
        except Exception as exc:
            _log.exception("Background patients_details sync falhou (job=%s)", job_id)
            try:
                job = await session.get(SyncJob, job_id)
                if job is not None:
                    job.status = "error"
                    job.error_message = f"Background task crashed: {exc!r}"[:1000]
                    job.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()
            except Exception:
                _log.exception("Falha ao marcar job %s como error após crash", job_id)


@router.post("/clinicorp/patients/details", response_model=SyncJobResponse, status_code=200)
async def sync_clinicorp_patients_details(
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> SyncJobResponse:
    """Enriquece pacientes via /patient/get (sub-PR 18).

    Cria o SyncJob com status='running' e dispara o sync em background
    (asyncio.create_task com sessão DB própria). Retorna imediatamente
    o job — cliente faz polling em /sync/jobs pra ver progresso.

    Necessário porque o sync sequencial pode levar 10-30+ min e o
    request HTTP estouraria timeout muito antes (deixando coroutine órfã).
    Idempotente — atualiza em vez de duplicar. skip_existing por padrão.
    """
    tenant_id = _require_tenant(current_user)

    job = SyncJob(
        tenant_id=tenant_id,
        source="clinicorp",
        entity="patients_details",
        status="running",
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    asyncio.create_task(_run_patients_details_in_background(tenant_id, job.id))

    return SyncJobResponse.model_validate(job)


@router.post("/clinicorp/transactional", response_model=SyncJobResponse, status_code=200)
async def sync_clinicorp_transactional(
    payload: TransactionalSyncRequest,
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> SyncJobResponse:
    """Sincroniza UMA entidade transacional cobrindo o mês indicado."""
    tenant_id = _require_tenant(current_user)
    try:
        spec = get_entity_spec(payload.entity)
        if spec not in TRANSACTIONAL_ENTITIES:
            raise ValueError(f"Entidade '{payload.entity}' não é transacional.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        job = await sync_transactional_entity(db, tenant_id, spec, payload.year, payload.month)
    except ValueError as exc:  # ex: mês ainda não começou
        raise HTTPException(status_code=400, detail=str(exc))

    return SyncJobResponse.model_validate(job)


@router.post("/clinicorp/transactional/batch", response_model=TransactionalSyncResponse, status_code=200)
async def sync_clinicorp_transactional_batch(
    payload: TransactionalBatchRequest,
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> TransactionalSyncResponse:
    """Sincroniza várias entidades transacionais num único mês."""
    tenant_id = _require_tenant(current_user)
    try:
        jobs = await sync_transactional_batch(
            db, tenant_id, payload.year, payload.month, payload.entities,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return TransactionalSyncResponse(
        jobs=[SyncJobResponse.model_validate(j) for j in jobs],
        total_inserted=sum(j.records_inserted or 0 for j in jobs),
        total_updated=sum(j.records_updated or 0 for j in jobs),
        total_errors=sum(j.errors_count or 0 for j in jobs),
    )


@router.post("/contaazul/static", response_model=StaticSyncResponse, status_code=200)
async def sync_contaazul_static(
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> StaticSyncResponse:
    """Sync das 4 entidades estáticas Conta Azul (pessoas, produtos, servicos, vendedores)."""
    tenant_id = _require_tenant(current_user)
    jobs = await ca_sync.sync_all_static(db, tenant_id)
    return StaticSyncResponse(
        jobs=[SyncJobResponse.model_validate(j) for j in jobs],
        total_inserted=sum(j.records_inserted or 0 for j in jobs),
        total_updated=sum(j.records_updated or 0 for j in jobs),
        total_errors=sum(j.errors_count or 0 for j in jobs),
    )


@router.post("/contaazul/financial", response_model=TransactionalSyncResponse, status_code=200)
async def sync_contaazul_financial(
    payload: KpisMonthlyRequest,
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> TransactionalSyncResponse:
    """Sync de contas a receber + contas a pagar do mês indicado."""
    tenant_id = _require_tenant(current_user)
    try:
        jobs = await ca_sync.sync_transactional_batch(
            db, tenant_id, payload.year, payload.month,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return TransactionalSyncResponse(
        jobs=[SyncJobResponse.model_validate(j) for j in jobs],
        total_inserted=sum(j.records_inserted or 0 for j in jobs),
        total_updated=sum(j.records_updated or 0 for j in jobs),
        total_errors=sum(j.errors_count or 0 for j in jobs),
    )


@router.post("/contaazul/transactional", response_model=SyncJobResponse, status_code=200)
async def sync_contaazul_transactional(
    payload: TransactionalSyncRequest,
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> SyncJobResponse:
    """Sync de UMA entidade transacional CA (contas_receber ou contas_pagar) num mês."""
    tenant_id = _require_tenant(current_user)
    try:
        spec = ca_sync.get_entity_spec(payload.entity)
        if spec not in ca_sync.TRANSACTIONAL_ENTITIES:
            raise HTTPException(
                status_code=400,
                detail=f"Entidade '{payload.entity}' não é transacional no Conta Azul.",
            )
        job = await ca_sync.sync_transactional_entity(
            db, tenant_id, spec, payload.year, payload.month,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return SyncJobResponse.model_validate(job)


@router.post("/contaazul/historical", response_model=TransactionalSyncResponse, status_code=200)
async def sync_contaazul_historical(
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> TransactionalSyncResponse:
    """Carga histórica COMPLETA — varre desde 2020 até hoje, mês a mês,
    cobrindo TODAS as parcelas (a receber + a pagar).

    Necessário porque o `/buscar` do CA não filtra por `data_pagamento` —
    parcelas pagas em abr/26 com vencimento em jan/24 ficam invisíveis no
    sync mensal normal. Roda em ~1min pra Parente.

    Idempotente — pode rodar quantas vezes quiser. Após a primeira carga,
    use a sync delta (`/contaazul/alteracoes`) pra updates incrementais.
    """
    tenant_id = _require_tenant(current_user)
    jobs = await ca_sync.sync_historical_contaazul(db, tenant_id)
    return TransactionalSyncResponse(
        jobs=[SyncJobResponse.model_validate(j) for j in jobs],
        total_inserted=sum(j.records_inserted or 0 for j in jobs),
        total_updated=sum(j.records_updated or 0 for j in jobs),
        total_errors=sum(j.errors_count or 0 for j in jobs),
    )


@router.post("/contaazul/baixas", response_model=SyncJobResponse, status_code=200)
async def sync_contaazul_baixas(
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> SyncJobResponse:
    """Detalha parcelas pagas via /parcelas/{id} pra capturar:
    metodo_pagamento, data_pagamento real, conta_destino, conciliado.

    Idempotente — só processa parcelas pagas que ainda não têm detalhe
    em staging. 1 chamada por parcela, semaphore=3 + retry 429. Para
    Parente (~5500 parcelas pagas), 1ª carga ~30-40min.
    """
    tenant_id = _require_tenant(current_user)
    job = await ca_sync.sync_baixas_parcelas(db, tenant_id, only_missing=True)
    return SyncJobResponse.model_validate(job)


@router.post("/contaazul/saldos", response_model=TransactionalSyncResponse, status_code=200)
async def sync_contaazul_saldos(
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> TransactionalSyncResponse:
    """Sync dos saldos bancários (Fase 1 Show no Financeiro):

    - contas_financeiras (lista de bancos)
    - saldos_atuais (snapshot por conta, em paralelo via asyncio.gather)
    - saldos_iniciais (últimos 12 meses)

    Roda os 3 jobs em sequência. Saldo atual usa concorrência limitada
    (semaphore=8) pra não saturar o gateway CA.
    """
    tenant_id = _require_tenant(current_user)
    jobs = await ca_sync.sync_saldos_bancarios(db, tenant_id)
    return TransactionalSyncResponse(
        jobs=[SyncJobResponse.model_validate(j) for j in jobs],
        total_inserted=sum(j.records_inserted or 0 for j in jobs),
        total_updated=sum(j.records_updated or 0 for j in jobs),
        total_errors=sum(j.errors_count or 0 for j in jobs),
    )


@router.post("/contaazul/alteracoes", response_model=TransactionalSyncResponse, status_code=200)
async def sync_contaazul_alteracoes(
    payload: DeltaSyncRequest,
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> TransactionalSyncResponse:
    """Delta sync — atualiza staging com contas a receber/pagar alteradas
    nas últimas N horas (default 24, máximo 720 = 30 dias).

    Apenas 2 chamadas à API CA (1× receber + 1× pagar) com filtro
    `data_alteracao_de`. Útil pra manter staging atualizado durante o dia
    sem re-sincronizar meses completos.
    """
    tenant_id = _require_tenant(current_user)
    try:
        jobs = await ca_sync.sync_alteracoes_recentes(
            db, tenant_id, hours_back=payload.hours_back,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return TransactionalSyncResponse(
        jobs=[SyncJobResponse.model_validate(j) for j in jobs],
        total_inserted=sum(j.records_inserted or 0 for j in jobs),
        total_updated=sum(j.records_updated or 0 for j in jobs),
        total_errors=sum(j.errors_count or 0 for j in jobs),
    )


@router.post("/clinicorp/kpis_monthly", response_model=SyncJobResponse, status_code=200)
async def sync_clinicorp_kpis_monthly(
    payload: KpisMonthlyRequest,
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> SyncJobResponse:
    """
    Sincroniza os 10 endpoints agregados num único job mensal,
    com chamadas em paralelo. Grava 1 linha em stg_cc_kpis_monthly.
    """
    tenant_id = _require_tenant(current_user)
    try:
        job = await sync_kpis_monthly(db, tenant_id, payload.year, payload.month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return SyncJobResponse.model_validate(job)


@router.get("/jobs", response_model=List[SyncJobResponse])
async def list_sync_jobs(
    limit: int = 50,
    entity: str | None = None,
    year: int | None = None,
    source: str | None = None,
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> List[SyncJobResponse]:
    """
    Lista jobs de sync do tenant.
    - `limit` (default 50): número máximo de jobs.
    - `entity` (opcional): filtra por nome da entidade.
    - `year` (opcional): filtra jobs cujo period_from caia no ano (heatmap).
    - `source` (opcional): 'clinicorp' | 'contaazul'.
    """
    from datetime import date as _date
    tenant_id = _require_tenant(current_user)
    stmt = select(SyncJob).where(SyncJob.tenant_id == tenant_id)
    if entity:
        stmt = stmt.where(SyncJob.entity == entity)
    if source:
        stmt = stmt.where(SyncJob.source == source)
    if year is not None:
        stmt = stmt.where(
            SyncJob.period_from >= _date(year, 1, 1),
            SyncJob.period_from <= _date(year, 12, 31),
        )
    stmt = stmt.order_by(desc(SyncJob.created_at)).limit(limit)
    result = await db.execute(stmt)
    return [SyncJobResponse.model_validate(j) for j in result.scalars().all()]


@router.get("/checkpoints", response_model=List[CheckpointResponse])
async def list_checkpoints(
    source: str | None = None,
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> List[CheckpointResponse]:
    """Estado atual de sync por entidade do tenant. Filtra por `source` opcional."""
    tenant_id = _require_tenant(current_user)
    stmt = select(SyncCheckpoint).where(SyncCheckpoint.tenant_id == tenant_id)
    if source:
        stmt = stmt.where(SyncCheckpoint.source == source)
    result = await db.execute(stmt)
    return [CheckpointResponse.model_validate(c) for c in result.scalars().all()]
