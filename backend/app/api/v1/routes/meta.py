"""
Rotas de configuração Meta — Sub-PR 21b.

GET    /meta/status         — status da conexão Meta do tenant
PUT    /meta/token          — salva/atualiza System User Token + IDs vinculados
POST   /meta/validate       — chama Graph API, devolve diagnóstico (semáforo)
DELETE /meta/token          — remove configuração Meta do tenant

Permissions: `empresa.settings.read` para GET, `empresa.settings.write` para
mutações (mesma matriz usada por Conta Azul).

A tabela `stg_meta_tokens` é multi-tenant — UK por (tenant_id) garante 1 linha
por clínica. O token NÃO é retornado em nenhum response.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.permissions import requires
from app.db.session import get_db
from app.integrations.meta.client import MetaGraphClient, MetaGraphError
from app.integrations.meta.sync_service import (
    MetaSyncError,
    SYNCERS,
    sync_all_available,
)
from app.models.staging_meta import (
    StgMetaFbPage,
    StgMetaIgPerfil,
    StgMetaPixel,
    StgMetaTokens,
)
from app.schemas.auth import UserMe
from app.schemas.meta import (
    MetaDashboardCard,
    MetaDashboardResponse,
    MetaPendingItem,
    MetaStatusResponse,
    MetaTokenIn,
    MetaValidationCheck,
    MetaValidationResponse,
)

router = APIRouter(prefix="/meta", tags=["meta"])


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _get_record(db: AsyncSession, tenant_id: str) -> StgMetaTokens | None:
    result = await db.execute(
        select(StgMetaTokens).where(StgMetaTokens.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


def _to_status(record: StgMetaTokens | None) -> MetaStatusResponse:
    if not record:
        return MetaStatusResponse(connected=False, status="desconectado")
    return MetaStatusResponse(
        connected=bool(record.token_is_valid),
        status="ativo" if record.token_is_valid else "token_invalido",
        token_validated_at=record.token_validated_at,
        token_is_valid=bool(record.token_is_valid),
        app_id=record.app_id,
        app_name=record.app_name,
        business_id=record.business_id,
        business_name=record.business_name,
        system_user_id=record.system_user_id,
        system_user_name=record.system_user_name,
        fb_page_id=record.fb_page_id,
        fb_page_name=record.fb_page_name,
        ig_account_id=record.ig_account_id,
        ig_username=record.ig_username,
        ad_account_id=record.ad_account_id,
        ad_account_authorized=bool(record.ad_account_authorized),
        pixel_id=record.pixel_id,
        pixel_last_fired_at=record.pixel_last_fired_at,
        token_scopes=record.token_scopes if isinstance(record.token_scopes, list) else None,
        graph_api_version=record.graph_api_version,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("/status", response_model=MetaStatusResponse)
async def meta_status(
    current_user: UserMe = Depends(requires("empresa.settings.read")),
    db: AsyncSession = Depends(get_db),
) -> MetaStatusResponse:
    """Estado atual da configuração Meta para o tenant logado."""
    record = await _get_record(db, current_user.tenant_id)
    return _to_status(record)


@router.put("/token", response_model=MetaStatusResponse)
async def meta_put_token(
    payload: MetaTokenIn,
    current_user: UserMe = Depends(requires("empresa.settings.write")),
    db: AsyncSession = Depends(get_db),
) -> MetaStatusResponse:
    """Upsert do registro Meta do tenant.

    Quando a UI quer "trocar de token" basta enviar o payload — campos vazios
    sobrescrevem com NULL (UI mostra antes do submit quais campos serão limpos).
    Após salvar, a UI deve chamar POST /meta/validate para confirmar acesso.
    """
    record = await _get_record(db, current_user.tenant_id)
    if record is None:
        record = StgMetaTokens(tenant_id=current_user.tenant_id, app_id=payload.app_id,
                               system_user_token=payload.system_user_token)
        db.add(record)

    record.app_id = payload.app_id
    record.app_name = payload.app_name
    record.business_id = payload.business_id
    record.business_name = payload.business_name
    record.system_user_token = payload.system_user_token
    record.system_user_id = payload.system_user_id
    record.system_user_name = payload.system_user_name
    record.fb_page_id = payload.fb_page_id
    record.fb_page_name = payload.fb_page_name
    record.fb_page_token = payload.fb_page_token
    record.ig_account_id = payload.ig_account_id
    record.ig_username = payload.ig_username
    record.ad_account_id = payload.ad_account_id
    record.pixel_id = payload.pixel_id
    record.is_active = True
    # Invalida validação anterior — o tenant precisa re-validar.
    record.token_is_valid = False
    record.token_validated_at = None
    record.ad_account_authorized = False

    await db.commit()
    await db.refresh(record)
    return _to_status(record)


@router.post("/validate", response_model=MetaValidationResponse)
async def meta_validate(
    current_user: UserMe = Depends(requires("empresa.settings.write")),
    db: AsyncSession = Depends(get_db),
) -> MetaValidationResponse:
    """Valida o token salvo via Graph API e popula `token_scopes`, `system_user_*`,
    `business_name`, `pixel_last_fired_at`, `ad_account_authorized`.

    Retorna um diagnóstico granular (`checks`) que a UI renderiza como semáforo.
    NÃO bloqueia se a Ad Account não estiver autorizada — apenas marca o check
    como vermelho (esse é o caso real da Parente hoje).
    """
    record = await _get_record(db, current_user.tenant_id)
    if not record:
        raise HTTPException(status_code=404, detail="Token Meta não cadastrado.")

    client = MetaGraphClient(record.system_user_token)
    checks: list[MetaValidationCheck] = []
    token_valid = False
    scopes: list[str] = []
    app_id: str | None = None
    su_id: str | None = None
    su_name: str | None = None

    # 1. Debug token
    try:
        debug = await client.debug_token()
        data = debug.get("data") if isinstance(debug, dict) else None
        if isinstance(data, dict):
            token_valid = bool(data.get("is_valid"))
            scopes = list(data.get("scopes") or [])
            app_id = data.get("app_id") or record.app_id
            su_id = data.get("user_id") or record.system_user_id
        checks.append(MetaValidationCheck(
            ok=token_valid, label="Token válido",
            detail=None if token_valid else "Token expirado ou revogado pelo Meta.",
        ))
    except MetaGraphError as exc:
        checks.append(MetaValidationCheck(ok=False, label="Token válido", detail=str(exc)))

    # 2. /me (nome do System User)
    if token_valid:
        try:
            me = await client.get_me()
            su_id = me.get("id") or su_id
            su_name = me.get("name")
            checks.append(MetaValidationCheck(
                ok=True, label="System User", detail=f"{su_name} ({su_id})",
            ))
        except MetaGraphError as exc:
            checks.append(MetaValidationCheck(ok=False, label="System User", detail=str(exc)))

    # 3. Business (opcional — só se cadastrado)
    biz_name = record.business_name
    if token_valid and record.business_id:
        try:
            biz = await client.get_business(record.business_id)
            biz_name = biz.get("name") or biz_name
            checks.append(MetaValidationCheck(
                ok=True, label="Business Manager",
                detail=f"{biz_name} (verif: {biz.get('verification_status') or 'n/a'})",
            ))
        except MetaGraphError as exc:
            checks.append(MetaValidationCheck(ok=False, label="Business Manager", detail=str(exc)))

    # 4. FB Page + IG vinculado (via /me/accounts)
    if token_valid and record.fb_page_id:
        try:
            pages = await client.get_my_pages()
            items = pages.get("data") if isinstance(pages, dict) else []
            match = next((p for p in items if str(p.get("id")) == str(record.fb_page_id)), None)
            if match:
                record.fb_page_token = match.get("access_token") or record.fb_page_token
                record.fb_page_name = match.get("name") or record.fb_page_name
                ig = match.get("instagram_business_account") or {}
                if ig.get("id") and not record.ig_account_id:
                    record.ig_account_id = ig.get("id")
                if ig.get("username") and not record.ig_username:
                    record.ig_username = ig.get("username")
                checks.append(MetaValidationCheck(
                    ok=True, label="Facebook Page",
                    detail=f"{record.fb_page_name} ({record.fb_page_id})",
                ))
                if record.ig_account_id:
                    checks.append(MetaValidationCheck(
                        ok=True, label="Instagram vinculado",
                        detail=f"@{record.ig_username or '?'} ({record.ig_account_id})",
                    ))
                else:
                    checks.append(MetaValidationCheck(
                        ok=False, label="Instagram vinculado",
                        detail="A Page não tem IG Business vinculado.",
                    ))
            else:
                checks.append(MetaValidationCheck(
                    ok=False, label="Facebook Page",
                    detail=f"Page {record.fb_page_id} não está na lista de pages do System User.",
                ))
        except MetaGraphError as exc:
            checks.append(MetaValidationCheck(ok=False, label="Facebook Page", detail=str(exc)))

    # 5. Ad Account
    if token_valid and record.ad_account_id:
        try:
            ad = await client.get_ad_account(record.ad_account_id)
            record.ad_account_authorized = True
            checks.append(MetaValidationCheck(
                ok=True, label="Ad Account",
                detail=f"{ad.get('name')} ({record.ad_account_id})",
            ))
        except MetaGraphError as exc:
            record.ad_account_authorized = False
            checks.append(MetaValidationCheck(
                ok=False, label="Ad Account",
                detail=f"{exc} — autorize o System User no Business Manager.",
            ))

    # 6. Pixel
    if token_valid and record.pixel_id:
        try:
            pixel = await client.get_pixel(record.pixel_id)
            last_fired = pixel.get("last_fired_time")
            if last_fired:
                try:
                    record.pixel_last_fired_at = datetime.fromisoformat(
                        last_fired.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except (ValueError, AttributeError):
                    pass
            unavailable = bool(pixel.get("is_unavailable"))
            detail = f"{pixel.get('name')} — último disparo: {last_fired or 'nunca'}"
            checks.append(MetaValidationCheck(
                ok=not unavailable, label="Pixel", detail=detail,
            ))
        except MetaGraphError as exc:
            checks.append(MetaValidationCheck(ok=False, label="Pixel", detail=str(exc)))

    await client.aclose()

    # Persiste descobertas
    record.token_is_valid = token_valid
    record.token_validated_at = _now_utc()
    record.token_scopes = scopes or None
    if app_id:
        record.app_id = app_id
    if su_id:
        record.system_user_id = su_id
    if su_name:
        record.system_user_name = su_name
    if biz_name:
        record.business_name = biz_name
    await db.commit()
    await db.refresh(record)

    return MetaValidationResponse(
        token_valid=token_valid,
        scopes=scopes,
        app_id=app_id,
        system_user_id=su_id,
        system_user_name=su_name,
        checks=checks,
        status=_to_status(record),
    )


@router.delete("/token", status_code=204)
async def meta_delete_token(
    current_user: UserMe = Depends(requires("empresa.settings.write")),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a configuração Meta do tenant."""
    await db.execute(
        delete(StgMetaTokens).where(StgMetaTokens.tenant_id == current_user.tenant_id)
    )
    await db.commit()


# ============================================================
# Sync — Sub-PR 21c
# ============================================================
# IMPORTANTE: declare /sync/all ANTES de /sync/{entity}, senão "all" é
# capturado como parâmetro pelo path variável.
@router.post("/sync/all")
async def meta_sync_all(
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Roda todos os syncs disponíveis em sequência. Erros parciais não bloqueiam:
    retorna `{ok: {...}, errors: {...}}` para a UI mostrar o que rodou e o que falhou.
    """
    return await sync_all_available(db, current_user.tenant_id)


# ============================================================
# Dashboard /marketing/visao-geral — Sub-PR 21d
# ============================================================
async def _latest_snapshot(db: AsyncSession, model, tenant_id: str):
    """Snapshot mais recente (maior data_referencia) p/ um canal do tenant."""
    result = await db.execute(
        select(model)
        .where(model.tenant_id == tenant_id)
        .order_by(model.data_referencia.desc(), model.synced_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _ig_card(snap) -> MetaDashboardCard:
    if not snap:
        return MetaDashboardCard(available=False)
    raw = snap.raw_data or {}
    return MetaDashboardCard(
        available=True,
        snapshot_date=snap.synced_at,
        username=raw.get("username"),
        display_name=raw.get("name"),
        profile_picture_url=raw.get("profile_picture_url"),
        followers=raw.get("followers_count"),
        follows=raw.get("follows_count"),
        total_posts=raw.get("media_count"),
        website=raw.get("website"),
        biografia=raw.get("biography"),
    )


def _fb_card(snap) -> MetaDashboardCard:
    if not snap:
        return MetaDashboardCard(available=False)
    raw = snap.raw_data or {}
    return MetaDashboardCard(
        available=True,
        snapshot_date=snap.synced_at,
        username=raw.get("username"),
        display_name=raw.get("name"),
        followers=raw.get("followers_count"),
        fan_count=raw.get("fan_count"),
        category=raw.get("category"),
        verification_status=raw.get("verification_status"),
        website=raw.get("website"),
        biografia=raw.get("about") or raw.get("description"),
    )


def _pixel_card(snap) -> MetaDashboardCard:
    if not snap:
        return MetaDashboardCard(available=False)
    raw = snap.raw_data or {}
    last = snap.external_updated_at
    days_idle = None
    if last:
        days_idle = (datetime.utcnow() - last).days
    return MetaDashboardCard(
        available=True,
        snapshot_date=snap.synced_at,
        pixel_name=raw.get("name"),
        pixel_last_fired_at=last,
        pixel_days_idle=days_idle,
        pixel_is_unavailable=bool(raw.get("is_unavailable")),
    )


def _build_pending(token: StgMetaTokens | None, scopes: list[str], pixel_days_idle: int | None) -> list[MetaPendingItem]:
    """Monta a checklist do que falta. Cada item é só mostrado se a condição
    correspondente NÃO estiver satisfeita — checklist se autolimpa conforme TI
    destrava as coisas."""
    items: list[MetaPendingItem] = []
    sset = set(scopes)
    if not token:
        return items

    if "instagram_basic" not in sset:
        items.append(MetaPendingItem(
            key="ig_basic",
            label="Permissão Instagram básico",
            detail="App IANALISYS precisa solicitar `instagram_basic` no App Review.",
            blocked_features=["Posts Instagram", "Stories"],
        ))
    if "instagram_manage_insights" not in sset:
        items.append(MetaPendingItem(
            key="ig_insights",
            label="Permissão Instagram Insights",
            detail="Solicitar `instagram_manage_insights` no App Review (1-3 dias úteis).",
            blocked_features=["Alcance orgânico", "Impressões", "Visualizações de perfil"],
        ))
    if "instagram_manage_comments" not in sset:
        items.append(MetaPendingItem(
            key="ig_comments",
            label="Permissão Instagram Comentários",
            detail="Solicitar `instagram_manage_comments` no App Review.",
            blocked_features=["Leitura de comentários", "IA de leads quentes"],
        ))
    if "read_insights" not in sset:
        items.append(MetaPendingItem(
            key="fb_insights",
            label="Permissão Facebook Insights",
            detail="Solicitar `read_insights` no App Review (geralmente auto-aprovado).",
            blocked_features=["Alcance Facebook", "Engagement por post FB"],
        ))
    if "pages_read_engagement" in sset and token.fb_page_id and not token.fb_page_token:
        # Permissão existe mas page_token não foi populado — basta re-validar
        items.append(MetaPendingItem(
            key="fb_page_token",
            label="Re-validar conexão Facebook",
            detail="Rode “Validar via Graph API” em /empresa/meta-config pra capturar o page token.",
            blocked_features=["Posts Facebook"],
        ))
    if token.ad_account_id and not token.ad_account_authorized:
        items.append(MetaPendingItem(
            key="ads_auth",
            label="Autorizar Ad Account no Business Manager",
            detail=f"Conta `{token.ad_account_id}` não autorizou o System User. Adicionar ativo no BM.",
            blocked_features=["Campanhas", "Anúncios", "Insights de anúncios", "Lead Forms", "Leads"],
        ))
    if token.pixel_id and pixel_days_idle is not None and pixel_days_idle > 30:
        items.append(MetaPendingItem(
            key="pixel_install",
            label="Reinstalar Pixel no site",
            detail=f"Pixel não dispara há {pixel_days_idle} dias. Reinstalar código no <head> de todas as páginas.",
            blocked_features=["Conversões", "Audiências de remarketing", "Funil anúncio→consulta"],
        ))
    return items


@router.get("/dashboard", response_model=MetaDashboardResponse)
async def meta_dashboard(
    current_user: UserMe = Depends(requires("empresa.settings.read")),
    db: AsyncSession = Depends(get_db),
) -> MetaDashboardResponse:
    """Visão geral Meta para o painel /marketing/visao-geral.

    Lê os 3 snapshots mais recentes (IG perfil, FB page, Pixel) e monta a
    checklist do que falta a TI destravar. A página se preenche automaticamente
    conforme novos syncs forem rodando.
    """
    tenant_id = current_user.tenant_id
    token = (await db.execute(
        select(StgMetaTokens).where(StgMetaTokens.tenant_id == tenant_id)
    )).scalar_one_or_none()

    ig_snap = await _latest_snapshot(db, StgMetaIgPerfil, tenant_id)
    fb_snap = await _latest_snapshot(db, StgMetaFbPage, tenant_id)
    pixel_snap = await _latest_snapshot(db, StgMetaPixel, tenant_id)

    ig_card = _ig_card(ig_snap)
    fb_card = _fb_card(fb_snap)
    pixel_card = _pixel_card(pixel_snap)

    scopes = (token.token_scopes or []) if token else []
    if not isinstance(scopes, list):
        scopes = []
    pending = _build_pending(token, scopes, pixel_card.pixel_days_idle)

    return MetaDashboardResponse(
        has_connection=bool(token and token.token_is_valid),
        token_validated_at=token.token_validated_at if token else None,
        business_name=token.business_name if token else None,
        instagram=ig_card,
        facebook=fb_card,
        pixel=pixel_card,
        pending=pending,
    )


@router.post("/sync/{entity}")
async def meta_sync_entity(
    entity: str,
    current_user: UserMe = Depends(requires("sync.run")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Sincroniza UMA entidade Meta (ig_profile, ig_media, fb_page, fb_posts, pixel).

    Entidades dependentes de App Review / Ad Account auth (insights, comments,
    ads, leads) ainda não estão implementadas — aparecerão aqui nos sub-PRs
    21d/21f conforme TI da clínica destrava as permissions.
    """
    syncer = SYNCERS.get(entity)
    if not syncer:
        raise HTTPException(
            status_code=400,
            detail=f"Entidade desconhecida: {entity}. Válidas: {list(SYNCERS.keys())}",
        )
    try:
        return await syncer(db, current_user.tenant_id)
    except MetaSyncError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
