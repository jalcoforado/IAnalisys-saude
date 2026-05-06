"""
Sync iterativa de detalhes de pacientes (Clinicorp /patient/get).

Diferente das demais syncs (estáticas + transacionais por período), esta
chama 1 endpoint por paciente — não há /patient/list. Roda sob demanda
pra enriquecer core_patients com BirthDate, Email, Phone, OtherDocumentId
(CPF) e Status.

Concorrência limitada via asyncio.Semaphore (default 5) pra não estourar
rate limit da Clinicorp.

Erros individuais (404/400 etc) não derrubam o batch — apenas contam
em errors_count e o erro fica registrado no log.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.clinicorp.client import ClinicorpClient, ClinicorpError
from app.models.core import CorePatients
from app.models.staging import StgCcPatientsDetails
from app.models.sync_job import SyncJob

SOURCE = "clinicorp"
ENTITY = "patients_details"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _list_patient_ids(
    db: AsyncSession, tenant_id: str, skip_existing: bool = True,
) -> list[int]:
    """Pega external_ids de pacientes do tenant (core_patients).
    Filtra is_deleted=0 — não enriquecemos pacientes excluídos.

    Se skip_existing=True, exclui os que já estão em stg_cc_patients_details.
    Útil pra retomar de onde parou após erro de rate limit.
    """
    q = await db.execute(
        select(CorePatients.external_id)
        .where(CorePatients.tenant_id == tenant_id)
        .where(CorePatients.is_deleted == 0)  # type: ignore[arg-type]
    )
    all_ids = [int(r[0]) for r in q.all() if r[0] and str(r[0]).isdigit()]
    if not skip_existing or not all_ids:
        return all_ids
    existing_q = await db.execute(
        select(StgCcPatientsDetails.external_id)
        .where(StgCcPatientsDetails.tenant_id == tenant_id)
    )
    existing = {str(r[0]) for r in existing_q.all()}
    return [pid for pid in all_ids if str(pid) not in existing]


async def _upsert_payload(
    db: AsyncSession, tenant_id: str, external_id: str, payload: dict[str, Any],
) -> bool:
    """Upsert no staging. Retorna True se inseriu, False se atualizou.
    Implementação: comparar count antes/depois é caro; usamos INSERT...ON
    DUPLICATE KEY UPDATE e dependemos da contagem agregada do batch.
    """
    stmt = mysql_insert(StgCcPatientsDetails).values(
        tenant_id=tenant_id,
        external_id=external_id,
        external_updated_at=None,
        raw_data=payload,
        synced_at=_now(),
    )
    stmt = stmt.on_duplicate_key_update(
        raw_data=stmt.inserted.raw_data,
        synced_at=stmt.inserted.synced_at,
    )
    await db.execute(stmt)
    return True


async def sync_patients_details(
    db: AsyncSession,
    tenant_id: str,
    *,
    ids: list[int] | None = None,
    concurrency: int = 1,
    skip_existing: bool = True,
    existing_job_id: int | None = None,
) -> SyncJob:
    """Enriquece pacientes via /patient/get. Idempotente (upsert por external_id).

    Args:
      ids: subset opcional de external_ids. Se None, processa todos os
        pacientes do tenant em core_patients.
      concurrency: máximo de calls simultâneas (default 1 — Clinicorp dá
        429 rate limit acima de 1-2 sustentadas. Sequencial é o caminho
        mais robusto pra one-shot).
      skip_existing: pula pacientes que já estão em stg_cc_patients_details.
        True por default pra retomar de onde parou após erros transientes.
      existing_job_id: se passado, usa o SyncJob já criado (ex: pelo endpoint
        em background). Caso contrário cria um novo.
    """
    if existing_job_id is not None:
        existing = await db.get(SyncJob, existing_job_id)
        if existing is None:
            raise RuntimeError(f"SyncJob {existing_job_id} não encontrado")
        job = existing
        job_id = existing_job_id
    else:
        job = SyncJob(
            tenant_id=tenant_id, source=SOURCE, entity=ENTITY,
            status="running", started_at=_now(),
        )
        db.add(job)
        await db.flush()
        job_id = job.id

    target_ids = (
        ids if ids is not None
        else await _list_patient_ids(db, tenant_id, skip_existing=skip_existing)
    )
    total = len(target_ids)

    if total == 0:
        job.finished_at = _now()
        job.duration_ms = 0
        job.records_fetched = 0
        job.records_inserted = 0
        job.records_updated = 0
        job.errors_count = 0
        job.status = "success"
        await db.commit()
        return job

    client = ClinicorpClient()
    sem = asyncio.Semaphore(concurrency)
    fetched = 0
    errors = 0
    last_error: str | None = None
    lock = asyncio.Lock()  # protege escrita no DB (1 conexão)

    # Throttle de 0.6s entre cada chamada (mesmo com concurrency=1) evita
    # reincidir no rate limit da Clinicorp após hits anteriores. Empírico:
    # >1 req/s sustentado dá 429 em série.
    throttle_seconds = 0.6

    # Timeout duro por chamada — protege contra socket TCP do Clinicorp
    # que ocasionalmente pendura o coroutine indefinidamente (httpx timeout
    # interno não basta nesses casos degenerados).
    per_call_timeout = 25.0

    async def fetch_one(pid: int) -> dict[str, Any] | None:
        nonlocal fetched, errors, last_error
        async with sem:
            await asyncio.sleep(throttle_seconds)
            try:
                payload = await asyncio.wait_for(
                    client.get_patient(pid), timeout=per_call_timeout,
                )
            except asyncio.TimeoutError:
                async with lock:
                    errors += 1
                    last_error = f"PatientId={pid}: timeout {per_call_timeout}s"
                return None
            except ClinicorpError as exc:
                async with lock:
                    errors += 1
                    last_error = f"PatientId={pid}: {exc}"
                return None
            except Exception as exc:
                async with lock:
                    errors += 1
                    last_error = f"PatientId={pid}: {exc!r}"
                return None
            async with lock:
                fetched += 1
                await _upsert_payload(db, tenant_id, str(pid), payload)
            return payload

    # Chunks menores (50) pra commitar mais cedo e ver progresso. Com throttle
    # de 0.6s, 50 pacientes = ~30-40s por commit.
    chunk_size = 50
    for i in range(0, total, chunk_size):
        chunk = target_ids[i:i + chunk_size]
        await asyncio.gather(*(fetch_one(pid) for pid in chunk))
        await db.commit()

    finished = _now()
    job = await db.get(SyncJob, job_id)  # re-fetch (pode ter sido invalidado)
    if job is None:
        # Improvável, mas precaução de tipo
        raise RuntimeError("SyncJob desapareceu após commit")
    job.finished_at = finished
    if job.started_at:
        job.duration_ms = int((finished - job.started_at).total_seconds() * 1000)
    job.records_fetched = fetched
    job.records_inserted = fetched   # não distinguimos insert/update no upsert
    job.records_updated = 0
    job.errors_count = errors
    job.error_message = last_error
    job.status = "success" if errors == 0 else ("error" if fetched == 0 else "partial")
    await db.commit()
    return job
