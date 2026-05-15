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
    StgMetaFbPageInsights,
    StgMetaFbPostInsights,
    StgMetaFbPosts,
    StgMetaIgAccountInsights,
    StgMetaIgComments,
    StgMetaIgPerfil,
    StgMetaIgPostInsights,
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
# 6. IG POST INSIGHTS — métricas por post (lifetime, cumulativo)
# ============================================================
# Métricas validadas em v19 (REELS retornam algumas a mais; comuns a todos os
# tipos de mídia: reach, saved, likes, comments, shares, total_interactions).
_IG_POST_METRICS = ["reach", "saved", "likes", "comments", "shares", "total_interactions"]


def _epoch(d: date) -> int:
    from datetime import datetime as _dt
    return int(_dt(d.year, d.month, d.day).timestamp())


def _insights_values_to_dict(payload: dict) -> dict[str, Any]:
    """Achata `{data:[{name,values:[{value}]},...]}` para `{metric_name: value}`."""
    out: dict[str, Any] = {}
    for entry in payload.get("data") or []:
        name = entry.get("name")
        values = entry.get("values") or []
        if not name or not values:
            continue
        # post insights: 1 valor (lifetime). account/page insights: lista por dia (tratado separado)
        out[name] = values[-1].get("value") if values else None
    return out


async def sync_ig_post_insights(db: AsyncSession, tenant_id: str, *, limit: int = 25) -> dict[str, Any]:
    """Para cada post IG já em staging, busca métricas. Idempotente por (tenant, post, hoje)."""
    rec = await _get_token_record(db, tenant_id)

    # Pega últimos N posts do staging (precisamos buscar insights dos posts conhecidos)
    posts = (await db.execute(
        select(StgMetaIgPosts.external_id, StgMetaIgPosts.raw_data)
        .where(StgMetaIgPosts.tenant_id == tenant_id)
        .order_by(StgMetaIgPosts.posted_at.desc())
        .limit(limit)
    )).all()

    if not posts:
        raise MetaSyncError("Nenhum post IG em staging — rode sync_ig_media antes.")

    job = await _open_job(db, tenant_id, "ig_post_insights")
    client = MetaGraphClient(rec.system_user_token)
    today = date.today()
    count = 0
    errors: list[str] = []
    try:
        for post_external_id, _ in posts:
            try:
                resp = await client.get_ig_post_insights(post_external_id, _IG_POST_METRICS)
                metrics = _insights_values_to_dict(resp)
                stmt = mysql_insert(StgMetaIgPostInsights).values(
                    tenant_id=tenant_id,
                    external_id=f"{post_external_id}:{today.isoformat()}",
                    data_referencia=today,
                    post_external_id=post_external_id,
                    raw_data={"metrics": metrics, "raw": resp},
                    sync_job_id=job.id,
                )
                stmt = stmt.on_duplicate_key_update(
                    raw_data=stmt.inserted.raw_data,
                    sync_job_id=stmt.inserted.sync_job_id,
                    synced_at=datetime.utcnow(),
                )
                await db.execute(stmt)
                count += 1
            except MetaGraphError as exc:
                # Post pode não suportar todas as métricas (ex: foto vs reel) — registra e segue
                errors.append(f"{post_external_id}: {exc}")
        await _close_job(db, job, records=count, error="; ".join(errors[:3]) if errors and count == 0 else None)
        await db.commit()
        return {"entity": "ig_post_insights", "records": count, "job_id": job.id, "errors": len(errors)}
    finally:
        await client.aclose()


# ============================================================
# 7. FB POST INSIGHTS
# ============================================================
_FB_POST_METRICS = [
    "post_impressions_unique",
    "post_clicks",
    "post_reactions_by_type_total",
    "post_video_views",
]


async def sync_fb_post_insights(db: AsyncSession, tenant_id: str, *, limit: int = 25) -> dict[str, Any]:
    rec = await _get_token_record(db, tenant_id)
    if not rec.fb_page_token:
        raise MetaSyncError("fb_page_token não configurado — rode /meta/validate.")

    posts = (await db.execute(
        select(StgMetaFbPosts.external_id, StgMetaFbPosts.raw_data)
        .where(StgMetaFbPosts.tenant_id == tenant_id)
        .order_by(StgMetaFbPosts.posted_at.desc())
        .limit(limit)
    )).all()

    if not posts:
        raise MetaSyncError("Nenhum post FB em staging — rode sync_fb_posts antes.")

    job = await _open_job(db, tenant_id, "fb_post_insights")
    client = MetaGraphClient(rec.system_user_token)
    today = date.today()
    count = 0
    errors: list[str] = []
    try:
        for post_external_id, _ in posts:
            try:
                resp = await client.get_fb_post_insights(
                    post_external_id, rec.fb_page_token, _FB_POST_METRICS
                )
                metrics = _insights_values_to_dict(resp)
                stmt = mysql_insert(StgMetaFbPostInsights).values(
                    tenant_id=tenant_id,
                    external_id=f"{post_external_id}:{today.isoformat()}",
                    data_referencia=today,
                    post_external_id=post_external_id,
                    raw_data={"metrics": metrics, "raw": resp},
                    sync_job_id=job.id,
                )
                stmt = stmt.on_duplicate_key_update(
                    raw_data=stmt.inserted.raw_data,
                    sync_job_id=stmt.inserted.sync_job_id,
                    synced_at=datetime.utcnow(),
                )
                await db.execute(stmt)
                count += 1
            except MetaGraphError as exc:
                errors.append(f"{post_external_id}: {exc}")
        await _close_job(db, job, records=count, error="; ".join(errors[:3]) if errors and count == 0 else None)
        await db.commit()
        return {"entity": "fb_post_insights", "records": count, "job_id": job.id, "errors": len(errors)}
    finally:
        await client.aclose()


# ============================================================
# 8. IG ACCOUNT INSIGHTS — métricas diárias da conta (alcance, follower_count)
# ============================================================
_IG_ACCOUNT_METRICS = ["reach", "follower_count"]


async def sync_ig_account_insights(db: AsyncSession, tenant_id: str, *, days: int = 30) -> dict[str, Any]:
    rec = await _get_token_record(db, tenant_id)
    if not rec.ig_account_id:
        raise MetaSyncError("ig_account_id não configurado.")

    job = await _open_job(db, tenant_id, "ig_account_insights")
    client = MetaGraphClient(rec.system_user_token)
    today = date.today()
    since = _epoch(date.fromordinal(today.toordinal() - days))
    until = _epoch(today)
    count = 0
    try:
        # Cada métrica gera 1 série diária; achatamos pra 1 row (tenant, data, metric)
        for metric in _IG_ACCOUNT_METRICS:
            try:
                resp = await client.get_ig_account_insights_daily(
                    rec.ig_account_id, [metric], since_epoch=since, until_epoch=until
                )
                entries = resp.get("data") or []
                if not entries:
                    continue
                values = entries[0].get("values") or []
                for v in values:
                    end_time = v.get("end_time")
                    dt_ref = _parse_iso(end_time)
                    data_ref = dt_ref.date() if dt_ref else None
                    if not data_ref:
                        continue
                    stmt = mysql_insert(StgMetaIgAccountInsights).values(
                        tenant_id=tenant_id,
                        external_id=f"{rec.ig_account_id}:{metric}:{data_ref.isoformat()}",
                        data_referencia=data_ref,
                        metric_name=metric,
                        raw_data={"value": v.get("value"), "end_time": end_time, "metric": metric},
                        sync_job_id=job.id,
                    )
                    stmt = stmt.on_duplicate_key_update(
                        raw_data=stmt.inserted.raw_data,
                        sync_job_id=stmt.inserted.sync_job_id,
                        synced_at=datetime.utcnow(),
                    )
                    await db.execute(stmt)
                    count += 1
            except MetaGraphError:
                pass  # tolera métrica deprecada / sem dado
        await _close_job(db, job, records=count)
        await db.commit()
        return {"entity": "ig_account_insights", "records": count, "job_id": job.id}
    finally:
        await client.aclose()


# ============================================================
# 9. FB PAGE INSIGHTS — métricas diárias da Page
# ============================================================
_FB_PAGE_METRICS = [
    "page_impressions_unique",
    "page_post_engagements",
    "page_views_total",
    "page_video_views",
]


async def sync_fb_page_insights(db: AsyncSession, tenant_id: str, *, days: int = 30) -> dict[str, Any]:
    rec = await _get_token_record(db, tenant_id)
    if not rec.fb_page_id or not rec.fb_page_token:
        raise MetaSyncError("fb_page_id/fb_page_token não configurados.")

    job = await _open_job(db, tenant_id, "fb_page_insights")
    client = MetaGraphClient(rec.system_user_token)
    today = date.today()
    since = _epoch(date.fromordinal(today.toordinal() - days))
    until = _epoch(today)
    count = 0
    try:
        for metric in _FB_PAGE_METRICS:
            try:
                resp = await client.get_fb_page_insights_daily(
                    rec.fb_page_id, rec.fb_page_token, [metric],
                    since_epoch=since, until_epoch=until,
                )
                entries = resp.get("data") or []
                if not entries:
                    continue
                values = entries[0].get("values") or []
                for v in values:
                    end_time = v.get("end_time")
                    dt_ref = _parse_iso(end_time)
                    data_ref = dt_ref.date() if dt_ref else None
                    if not data_ref:
                        continue
                    stmt = mysql_insert(StgMetaFbPageInsights).values(
                        tenant_id=tenant_id,
                        external_id=f"{rec.fb_page_id}:{metric}:{data_ref.isoformat()}",
                        data_referencia=data_ref,
                        metric_name=metric,
                        raw_data={"value": v.get("value"), "end_time": end_time, "metric": metric},
                        sync_job_id=job.id,
                    )
                    stmt = stmt.on_duplicate_key_update(
                        raw_data=stmt.inserted.raw_data,
                        sync_job_id=stmt.inserted.sync_job_id,
                        synced_at=datetime.utcnow(),
                    )
                    await db.execute(stmt)
                    count += 1
            except MetaGraphError:
                pass
        await _close_job(db, job, records=count)
        await db.commit()
        return {"entity": "fb_page_insights", "records": count, "job_id": job.id}
    finally:
        await client.aclose()


# ============================================================
# 10. IG COMMENTS — comentários por post (Sub-PR 21f)
# ============================================================
async def sync_ig_comments(
    db: AsyncSession, tenant_id: str, *, posts_limit: int = 25, comments_per_post: int = 50,
) -> dict[str, Any]:
    """Para cada post IG em staging, busca comentários e grava em stg_meta_ig_comments.

    Idempotente por (tenant, external_id) — re-rodar não duplica. Tolera erro
    por post (alguns podem ter comentários desabilitados via `is_comment_enabled`).
    """
    rec = await _get_token_record(db, tenant_id)
    posts = (await db.execute(
        select(StgMetaIgPosts.external_id, StgMetaIgPosts.raw_data)
        .where(StgMetaIgPosts.tenant_id == tenant_id)
        .order_by(StgMetaIgPosts.posted_at.desc())
        .limit(posts_limit)
    )).all()
    if not posts:
        raise MetaSyncError("Nenhum post IG em staging — rode sync_ig_media antes.")

    job = await _open_job(db, tenant_id, "ig_comments")
    client = MetaGraphClient(rec.system_user_token)
    count = 0
    errors: list[str] = []
    try:
        for post_external_id, post_raw in posts:
            # Pula posts com comentários desabilitados (evita 400 do Graph)
            if (post_raw or {}).get("is_comment_enabled") is False:
                continue
            try:
                resp = await client.get_ig_post_comments(post_external_id, limit=comments_per_post)
                items = resp.get("data") or []
                for c in items:
                    commented_at = _parse_iso(c.get("timestamp"))
                    stmt = mysql_insert(StgMetaIgComments).values(
                        tenant_id=tenant_id,
                        external_id=str(c["id"]),
                        post_external_id=post_external_id,
                        commented_at=commented_at,
                        external_updated_at=commented_at,
                        raw_data=c,
                        sync_job_id=job.id,
                    )
                    stmt = stmt.on_duplicate_key_update(
                        commented_at=stmt.inserted.commented_at,
                        raw_data=stmt.inserted.raw_data,
                        sync_job_id=stmt.inserted.sync_job_id,
                        synced_at=datetime.utcnow(),
                    )
                    await db.execute(stmt)
                    count += 1
                    # Replies inline (1 nível)
                    replies = (c.get("replies") or {}).get("data") or []
                    for r in replies:
                        r_at = _parse_iso(r.get("timestamp"))
                        stmt_r = mysql_insert(StgMetaIgComments).values(
                            tenant_id=tenant_id,
                            external_id=str(r["id"]),
                            post_external_id=post_external_id,
                            commented_at=r_at,
                            external_updated_at=r_at,
                            raw_data={**r, "parent_id": c["id"]},
                            sync_job_id=job.id,
                        )
                        stmt_r = stmt_r.on_duplicate_key_update(
                            commented_at=stmt_r.inserted.commented_at,
                            raw_data=stmt_r.inserted.raw_data,
                            sync_job_id=stmt_r.inserted.sync_job_id,
                            synced_at=datetime.utcnow(),
                        )
                        await db.execute(stmt_r)
                        count += 1
            except MetaGraphError as exc:
                errors.append(f"{post_external_id}: {exc}")
        await _close_job(db, job, records=count, error="; ".join(errors[:3]) if errors and count == 0 else None)
        await db.commit()
        return {"entity": "ig_comments", "records": count, "job_id": job.id, "errors": len(errors)}
    finally:
        await client.aclose()


# ============================================================
# Orquestrador: roda tudo o que funciona com permissions atuais
# ============================================================
SYNCERS = {
    "ig_profile": sync_ig_profile,
    "ig_media": sync_ig_media,
    "ig_post_insights": sync_ig_post_insights,
    "ig_account_insights": sync_ig_account_insights,
    "ig_comments": sync_ig_comments,
    "fb_page": sync_fb_page,
    "fb_posts": sync_fb_posts,
    "fb_post_insights": sync_fb_post_insights,
    "fb_page_insights": sync_fb_page_insights,
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
