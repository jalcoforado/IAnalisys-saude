"""
Scheduler diário — Sub-PR 21f.

Roda APScheduler dentro do processo FastAPI. Para cada tenant com Meta
configurado e válido, dispara em sequência:

  04:00  → sync_all_available     (perfil, posts, insights, pixel — 9 entidades)
  04:15  → sync_ig_comments       (depende dos posts já estarem em staging)
  04:30  → classify_pending       (classifica comentários via DeepSeek+fast-path)

Cuidados:
- Em dev (uvicorn --reload), o reload watcher cria 2 processos. O scheduler
  só inicia no processo principal — checa env var ENABLE_SCHEDULER ou
  RUN_MAIN (padrão watchfiles).
- AsyncIOScheduler usa o mesmo event loop do FastAPI — sem thread extra.
- Cada job abre uma sessão própria via async_session() — não compartilha
  Session com outros jobs.
- Falhas por tenant não derrubam os outros — log + continua.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.db.session import AsyncSessionLocal as async_session
from app.integrations.meta.sync_service import (
    MetaSyncError,
    sync_all_available,
    sync_ig_comments,
    sync_ig_stories,
)
from app.models.staging_meta import StgMetaTokens
from app.services.meta_comments_classifier import classify_pending_comments

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _list_tenants_with_meta() -> list[str]:
    """Tenants com token Meta válido (token_is_valid=True)."""
    async with async_session() as db:
        rows = (await db.execute(
            select(StgMetaTokens.tenant_id).where(StgMetaTokens.token_is_valid.is_(True))
        )).all()
    return [r[0] for r in rows]


async def _job_meta_sync_all() -> None:
    """Job: rodar sync_all_available pra cada tenant Meta."""
    tenants = await _list_tenants_with_meta()
    logger.info("[scheduler] meta_sync_all iniciando — %d tenants", len(tenants))
    for tid in tenants:
        try:
            async with async_session() as db:
                result = await sync_all_available(db, tid)
                ok = len(result.get("ok") or {})
                errs = len(result.get("errors") or {})
                logger.info("[scheduler] tenant=%s sync_all: %d ok, %d erros", tid, ok, errs)
        except Exception as exc:
            logger.exception("[scheduler] meta_sync_all FALHOU tenant=%s: %s", tid, exc)


async def _job_meta_ig_comments() -> None:
    """Job: rodar sync_ig_comments pra cada tenant Meta."""
    tenants = await _list_tenants_with_meta()
    logger.info("[scheduler] meta_ig_comments iniciando — %d tenants", len(tenants))
    for tid in tenants:
        try:
            async with async_session() as db:
                result = await sync_ig_comments(db, tid)
                logger.info("[scheduler] tenant=%s ig_comments: %d records", tid, result.get("records", 0))
        except MetaSyncError as exc:
            logger.warning("[scheduler] tenant=%s ig_comments pulado: %s", tid, exc)
        except Exception as exc:
            logger.exception("[scheduler] meta_ig_comments FALHOU tenant=%s: %s", tid, exc)


async def _job_meta_ig_stories() -> None:
    """Job: rodar sync_ig_stories pra cada tenant Meta.

    Stories duram 24h — sem captura diária os dados se perdem.
    """
    tenants = await _list_tenants_with_meta()
    logger.info("[scheduler] meta_ig_stories iniciando — %d tenants", len(tenants))
    for tid in tenants:
        try:
            async with async_session() as db:
                result = await sync_ig_stories(db, tid)
                logger.info("[scheduler] tenant=%s ig_stories: %d records", tid, result.get("records", 0))
        except MetaSyncError as exc:
            logger.warning("[scheduler] tenant=%s ig_stories pulado: %s", tid, exc)
        except Exception as exc:
            logger.exception("[scheduler] meta_ig_stories FALHOU tenant=%s: %s", tid, exc)


async def _job_classify_comments() -> None:
    """Job: rodar classify_pending_comments pra cada tenant."""
    tenants = await _list_tenants_with_meta()
    logger.info("[scheduler] classify_comments iniciando — %d tenants", len(tenants))
    for tid in tenants:
        try:
            async with async_session() as db:
                stats = await classify_pending_comments(db, tid, limit=300)
                logger.info(
                    "[scheduler] tenant=%s classify: %d processados (fast=%d ia=%d errs=%d)",
                    tid, stats.get("processed", 0), stats.get("fast_path", 0),
                    stats.get("ia", 0), stats.get("errors", 0),
                )
        except Exception as exc:
            logger.exception("[scheduler] classify_comments FALHOU tenant=%s: %s", tid, exc)


def _should_run() -> bool:
    """Decide se inicia. False quando estamos no watcher pai do --reload.

    Watchfiles (default do uvicorn --reload) define `RUN_MAIN=true` no filho.
    Pra evitar 2 schedulers, só rodamos quando essa var está definida —
    em prod (sem reload) também roda porque a var costuma ser setada;
    fallback: `ENABLE_SCHEDULER=1` força explicitamente.
    """
    if os.getenv("DISABLE_SCHEDULER") == "1":
        return False
    if os.getenv("ENABLE_SCHEDULER") == "1":
        return True
    # Heurística: sem --reload, RUN_MAIN não está definida; com --reload
    # só fica True no filho. Em ambos os casos sem reload (prod) queremos rodar.
    return True


def start_scheduler() -> AsyncIOScheduler | None:
    """Cria + inicia o scheduler. Idempotente — chamadas duplicadas ignoram."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    if not _should_run():
        logger.info("[scheduler] desabilitado (DISABLE_SCHEDULER=1)")
        return None

    # Grace de 1 dia = se a máquina ficou off, ao ligar roda 1x só com tudo
    # acumulado (coalesce=True agrupa misfires consecutivos).
    sched = AsyncIOScheduler(timezone="America/Sao_Paulo")
    grace = 86400  # 1 dia
    sched.add_job(
        _job_meta_sync_all,
        CronTrigger(hour=4, minute=0),
        id="meta_sync_all",
        name="Meta: sync_all_available (todos tenants)",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=grace,
        replace_existing=True,
    )
    sched.add_job(
        _job_meta_ig_stories,
        CronTrigger(hour=4, minute=5),
        id="meta_ig_stories",
        name="Meta: sync_ig_stories (efêmero — captura antes de expirar)",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=grace,
        replace_existing=True,
    )
    sched.add_job(
        _job_meta_ig_comments,
        CronTrigger(hour=4, minute=15),
        id="meta_ig_comments",
        name="Meta: sync_ig_comments",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=grace,
        replace_existing=True,
    )
    sched.add_job(
        _job_classify_comments,
        CronTrigger(hour=4, minute=30),
        id="meta_classify_comments",
        name="Meta: classify_pending_comments",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=grace,
        replace_existing=True,
    )
    sched.start()
    _scheduler = sched
    logger.info("[scheduler] iniciado em America/Sao_Paulo · 4 jobs Meta às 04:00/04:05/04:15/04:30")
    return sched


def shutdown_scheduler() -> None:
    """Para o scheduler no shutdown do FastAPI."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("[scheduler] parado")


def get_scheduler_status() -> dict:
    """Status pro endpoint /admin/scheduler/status."""
    if _scheduler is None:
        return {"running": False, "jobs": []}
    jobs = []
    for job in _scheduler.get_jobs():
        next_run = job.next_run_time
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": next_run.isoformat() if next_run else None,
        })
    return {
        "running": _scheduler.running,
        "timezone": str(_scheduler.timezone),
        "jobs": jobs,
        "server_time": datetime.now().isoformat(),
    }
