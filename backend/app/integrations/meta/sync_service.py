"""
Sync service Meta — Sub-PR 21c.

Implementa upserts STAGING para todas as entidades que funcionam HOJE com o
conjunto atual de permissions:
  - sync_ig_profile  → stg_meta_ig_perfil (snapshot diário)
  - sync_ig_media    → stg_meta_ig_posts
  - sync_fb_page     → stg_meta_fb_page (snapshot diário)
  - sync_fb_posts    → stg_meta_fb_posts
  - sync_pixel       → stg_meta_pixel (snapshot diário)

Entidades pendentes de App Review/autorização (instagram_manage_insights,
instagram_manage_comments, read_insights, Ad Account auth) ficam para
sub-PRs 21d/21f.

Padrão Clinicorp/CA:
  - 1 SyncJob por execução (provider='meta')
  - upsert idempotente via UK (tenant_id, external_id [+ data_referencia])
  - raw_data JSON guarda o payload completo (audit trail + insumo IA)
"""
from datetime import date, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.meta.client import MetaGraphClient, MetaGraphError
from app.models.staging_meta import (
    StgMetaFbPage,
    StgMetaFbPosts,
    StgMetaIgPerfil,
    StgMetaIgPosts,
    StgMetaPixel,
    StgMetaTokens,
)
from app.models.sync_job import SyncJob


class MetaSyncError(Exception):
    pass


def _parse_iso(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


async def _get_token_record(db: AsyncSession, tenant_id: str) -> StgMetaTokens:
    rec = (await db.execute(
        select(StgMetaTokens).where(StgMetaTokens.tenant_id == tenant_id)
    )).scalar_one_or_none()
    if not rec:
        raise MetaSyncError("Token Meta não cadastrado para este tenant.")
    if not rec.token_is_valid:
        raise MetaSyncError("Token Meta não validado. Valide via /meta/validate antes de sincronizar.")
    return rec


async def _open_job(db: AsyncSession, tenant_id: str, entity: str) -> SyncJob:
    job = SyncJob(
        tenant_id=tenant_id,
        source="meta",
        entity=entity,
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(job)
    await db.flush()  # garante job.id
    return job


async def _close_job(db: AsyncSession, job: SyncJob, *, records: int, error: str | None = None) -> None:
    job.status = "error" if error else "success"
    job.records_fetched = records
    job.records_inserted = records if not error else 0
    job.error_message = error
    job.finished_at = datetime.utcnow()
    if job.started_at:
        job.duration_ms = int((job.finished_at - job.started_at).total_seconds() * 1000)


# ============================================================
# 1. IG PROFILE — snapshot diário
# ============================================================
async def sync_ig_profile(db: AsyncSession, tenant_id: str) -> dict[str, Any]:
    rec = await _get_token_record(db, tenant_id)
    if not rec.ig_account_id:
        raise MetaSyncError("ig_account_id não configurado.")

    job = await _open_job(db, tenant_id, "ig_profile")
    client = MetaGraphClient(rec.system_user_token)
    try:
        data = await client.get_ig_profile_full(rec.ig_account_id)
        today = date.today()
        stmt = mysql_insert(StgMetaIgPerfil).values(
            tenant_id=tenant_id,
            external_id=str(data.get("id") or rec.ig_account_id),
            data_referencia=today,
            external_updated_at=None,
            raw_data=data,
            sync_job_id=job.id,
        )
        stmt = stmt.on_duplicate_key_update(
            raw_data=stmt.inserted.raw_data,
            sync_job_id=stmt.inserted.sync_job_id,
            synced_at=datetime.utcnow(),
        )
        await db.execute(stmt)
        await _close_job(db, job, records=1)
        await db.commit()
        return {"entity": "ig_profile", "records": 1, "job_id": job.id}
    except MetaGraphError as exc:
        await _close_job(db, job, records=0, error=str(exc))
        await db.commit()
        raise MetaSyncError(f"Graph API: {exc}") from exc
    finally:
        await client.aclose()


# ============================================================
# 2. IG MEDIA (posts)
# ============================================================
async def sync_ig_media(db: AsyncSession, tenant_id: str, *, limit: int = 25) -> dict[str, Any]:
    rec = await _get_token_record(db, tenant_id)
    if not rec.ig_account_id:
        raise MetaSyncError("ig_account_id não configurado.")

    job = await _open_job(db, tenant_id, "ig_media")
    client = MetaGraphClient(rec.system_user_token)
    try:
        resp = await client.get_ig_media(rec.ig_account_id, limit=limit)
        items = resp.get("data") or []
        count = 0
        for post in items:
            posted_at = _parse_iso(post.get("timestamp"))
            stmt = mysql_insert(StgMetaIgPosts).values(
                tenant_id=tenant_id,
                external_id=str(post["id"]),
                posted_at=posted_at,
                external_updated_at=posted_at,
                raw_data=post,
                sync_job_id=job.id,
            )
            stmt = stmt.on_duplicate_key_update(
                posted_at=stmt.inserted.posted_at,
                external_updated_at=stmt.inserted.external_updated_at,
                raw_data=stmt.inserted.raw_data,
                sync_job_id=stmt.inserted.sync_job_id,
                synced_at=datetime.utcnow(),
            )
            await db.execute(stmt)
            count += 1
        await _close_job(db, job, records=count)
        await db.commit()
        return {"entity": "ig_media", "records": count, "job_id": job.id}
    except MetaGraphError as exc:
        await _close_job(db, job, records=0, error=str(exc))
        await db.commit()
        raise MetaSyncError(f"Graph API: {exc}") from exc
    finally:
        await client.aclose()


# ============================================================
# 3. FB PAGE — snapshot diário
# ============================================================
async def sync_fb_page(db: AsyncSession, tenant_id: str) -> dict[str, Any]:
    rec = await _get_token_record(db, tenant_id)
    if not rec.fb_page_id or not rec.fb_page_token:
        raise MetaSyncError("fb_page_id/fb_page_token não configurados (rode /meta/validate primeiro).")

    job = await _open_job(db, tenant_id, "fb_page")
    client = MetaGraphClient(rec.system_user_token)
    try:
        data = await client.get_fb_page_full(rec.fb_page_id, rec.fb_page_token)
        today = date.today()
        stmt = mysql_insert(StgMetaFbPage).values(
            tenant_id=tenant_id,
            external_id=str(data.get("id") or rec.fb_page_id),
            data_referencia=today,
            external_updated_at=None,
            raw_data=data,
            sync_job_id=job.id,
        )
        stmt = stmt.on_duplicate_key_update(
            raw_data=stmt.inserted.raw_data,
            sync_job_id=stmt.inserted.sync_job_id,
            synced_at=datetime.utcnow(),
        )
        await db.execute(stmt)
        await _close_job(db, job, records=1)
        await db.commit()
        return {"entity": "fb_page", "records": 1, "job_id": job.id}
    except MetaGraphError as exc:
        await _close_job(db, job, records=0, error=str(exc))
        await db.commit()
        raise MetaSyncError(f"Graph API: {exc}") from exc
    finally:
        await client.aclose()


# ============================================================
# 4. FB POSTS
# ============================================================
async def sync_fb_posts(db: AsyncSession, tenant_id: str, *, limit: int = 25) -> dict[str, Any]:
    rec = await _get_token_record(db, tenant_id)
    if not rec.fb_page_id or not rec.fb_page_token:
        raise MetaSyncError("fb_page_id/fb_page_token não configurados.")

    job = await _open_job(db, tenant_id, "fb_posts")
    client = MetaGraphClient(rec.system_user_token)
    try:
        resp = await client.get_fb_posts(rec.fb_page_id, rec.fb_page_token, limit=limit)
        items = resp.get("data") or []
        count = 0
        for post in items:
            posted_at = _parse_iso(post.get("created_time"))
            stmt = mysql_insert(StgMetaFbPosts).values(
                tenant_id=tenant_id,
                external_id=str(post["id"]),
                posted_at=posted_at,
                external_updated_at=posted_at,
                raw_data=post,
                sync_job_id=job.id,
            )
            stmt = stmt.on_duplicate_key_update(
                posted_at=stmt.inserted.posted_at,
                external_updated_at=stmt.inserted.external_updated_at,
                raw_data=stmt.inserted.raw_data,
                sync_job_id=stmt.inserted.sync_job_id,
                synced_at=datetime.utcnow(),
            )
            await db.execute(stmt)
            count += 1
        await _close_job(db, job, records=count)
        await db.commit()
        return {"entity": "fb_posts", "records": count, "job_id": job.id}
    except MetaGraphError as exc:
        await _close_job(db, job, records=0, error=str(exc))
        await db.commit()
        raise MetaSyncError(f"Graph API: {exc}") from exc
    finally:
        await client.aclose()


# ============================================================
# 5. PIXEL — snapshot diário
# ============================================================
async def sync_pixel(db: AsyncSession, tenant_id: str) -> dict[str, Any]:
    rec = await _get_token_record(db, tenant_id)
    if not rec.pixel_id:
        raise MetaSyncError("pixel_id não configurado.")

    job = await _open_job(db, tenant_id, "pixel")
    client = MetaGraphClient(rec.system_user_token)
    try:
        data = await client.get_pixel_full(rec.pixel_id)
        today = date.today()
        last_fired = _parse_iso(data.get("last_fired_time"))
        stmt = mysql_insert(StgMetaPixel).values(
            tenant_id=tenant_id,
            external_id=str(data.get("id") or rec.pixel_id),
            data_referencia=today,
            external_updated_at=last_fired,
            raw_data=data,
            sync_job_id=job.id,
        )
        stmt = stmt.on_duplicate_key_update(
            external_updated_at=stmt.inserted.external_updated_at,
            raw_data=stmt.inserted.raw_data,
            sync_job_id=stmt.inserted.sync_job_id,
            synced_at=datetime.utcnow(),
        )
        await db.execute(stmt)
        # Atualiza também `pixel_last_fired_at` no registro de token (UI mostra)
        if last_fired:
            await db.execute(
                update(StgMetaTokens)
                .where(StgMetaTokens.tenant_id == tenant_id)
                .values(pixel_last_fired_at=last_fired)
            )
        await _close_job(db, job, records=1)
        await db.commit()
        return {"entity": "pixel", "records": 1, "job_id": job.id, "last_fired": last_fired.isoformat() if last_fired else None}
    except MetaGraphError as exc:
        await _close_job(db, job, records=0, error=str(exc))
        await db.commit()
        raise MetaSyncError(f"Graph API: {exc}") from exc
    finally:
        await client.aclose()


# ============================================================
# Orquestrador: roda tudo o que funciona com permissions atuais
# ============================================================
SYNCERS = {
    "ig_profile": sync_ig_profile,
    "ig_media": sync_ig_media,
    "fb_page": sync_fb_page,
    "fb_posts": sync_fb_posts,
    "pixel": sync_pixel,
}


async def sync_all_available(db: AsyncSession, tenant_id: str) -> dict[str, Any]:
    """Roda em sequência tudo o que funciona com as permissions atuais.

    Cada syncer é tolerante: se um falhar, registra o erro no SyncJob mas
    continua os outros (essencial para Ad Account/Pixel pendentes na Parente).
    """
    results = {}
    errors = {}
    for name, fn in SYNCERS.items():
        try:
            results[name] = await fn(db, tenant_id)
        except MetaSyncError as exc:
            errors[name] = str(exc)
    return {"ok": results, "errors": errors}
