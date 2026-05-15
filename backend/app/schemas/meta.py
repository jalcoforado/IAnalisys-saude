"""
Schemas Pydantic para o módulo Meta — Sub-PR 21b.

GET  /meta/status     → MetaStatusResponse
PUT  /meta/token      → MetaTokenIn  → MetaStatusResponse
POST /meta/validate   → MetaValidationResponse (chama Graph e devolve descobertas)
DELETE /meta/token    → 204
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MetaTokenIn(BaseModel):
    """Body de PUT /meta/token. Único campo obrigatório é o `system_user_token`.

    IDs vinculados podem ser descobertos via Graph (POST /validate). Tudo aqui
    é editável pelo tenant_admin via /empresa/meta-config.
    """
    app_id: str = Field(..., min_length=1, max_length=64)
    app_name: Optional[str] = Field(None, max_length=128)
    business_id: Optional[str] = Field(None, max_length=64)
    business_name: Optional[str] = Field(None, max_length=255)
    system_user_token: str = Field(..., min_length=20)
    system_user_id: Optional[str] = Field(None, max_length=64)
    system_user_name: Optional[str] = Field(None, max_length=128)
    fb_page_id: Optional[str] = Field(None, max_length=64)
    fb_page_name: Optional[str] = Field(None, max_length=255)
    fb_page_token: Optional[str] = Field(None, max_length=4096)
    ig_account_id: Optional[str] = Field(None, max_length=64)
    ig_username: Optional[str] = Field(None, max_length=128)
    ad_account_id: Optional[str] = Field(None, max_length=64)
    pixel_id: Optional[str] = Field(None, max_length=64)


class MetaStatusResponse(BaseModel):
    """Resposta de GET /meta/status. Não retorna o token cru — apenas booleans
    e os IDs configurados (que NÃO são secret)."""
    connected: bool
    status: str  # 'ativo' | 'token_invalido' | 'desconectado'
    token_validated_at: Optional[datetime] = None
    token_is_valid: bool = False
    # IDs vinculados (todos opcionais — UI mostra ausentes)
    app_id: Optional[str] = None
    app_name: Optional[str] = None
    business_id: Optional[str] = None
    business_name: Optional[str] = None
    system_user_id: Optional[str] = None
    system_user_name: Optional[str] = None
    fb_page_id: Optional[str] = None
    fb_page_name: Optional[str] = None
    ig_account_id: Optional[str] = None
    ig_username: Optional[str] = None
    ad_account_id: Optional[str] = None
    ad_account_authorized: bool = False
    pixel_id: Optional[str] = None
    pixel_last_fired_at: Optional[datetime] = None
    token_scopes: Optional[list[str]] = None
    graph_api_version: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MetaValidationCheck(BaseModel):
    """Um item do diagnóstico — cada IDs vinculado é validado individualmente."""
    ok: bool
    label: str
    detail: Optional[str] = None


class MetaValidationResponse(BaseModel):
    """Resultado de POST /meta/validate.

    `checks` é uma lista de diagnósticos por categoria (token, page, IG, ads, pixel)
    que a UI renderiza como semáforo. `status` reflete o estado consolidado.
    """
    token_valid: bool
    scopes: list[str] = []
    app_id: Optional[str] = None
    system_user_id: Optional[str] = None
    system_user_name: Optional[str] = None
    checks: list[MetaValidationCheck] = []
    status: MetaStatusResponse


# ============================================================
# Dashboard /marketing/visao-geral — Sub-PR 21d (versão mínima)
# ============================================================
class MetaTopPost(BaseModel):
    """Top post por reach (IG ou FB)."""
    post_external_id: str
    posted_at: Optional[datetime] = None
    caption: Optional[str] = None
    permalink: Optional[str] = None
    media_url: Optional[str] = None
    reach: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    engagement_total: Optional[int] = None


class MetaDashboardCard(BaseModel):
    """Um card de canal (IG/FB/Pixel) com o que dá pra mostrar hoje."""
    available: bool                          # tem snapshot recente?
    snapshot_date: Optional[datetime] = None
    # IG/FB
    username: Optional[str] = None
    display_name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    followers: Optional[int] = None
    follows: Optional[int] = None
    total_posts: Optional[int] = None
    fan_count: Optional[int] = None
    category: Optional[str] = None
    verification_status: Optional[str] = None
    website: Optional[str] = None
    biografia: Optional[str] = None
    # Insights agregados (últimos 7 dias)
    reach_7d: Optional[int] = None           # alcance somado nos últimos 7d
    engagement_7d: Optional[int] = None      # interações somadas (FB) ou likes+comments+shares (IG)
    followers_gained_7d: Optional[int] = None  # ganho líquido de seguidores 7d (só IG)
    posts_7d: Optional[int] = None           # quantidade de posts publicados nos últimos 7d
    # Comparativo semana anterior (dias 8-14 atrás)
    reach_7d_prev: Optional[int] = None
    engagement_7d_prev: Optional[int] = None
    followers_gained_7d_prev: Optional[int] = None
    posts_7d_prev: Optional[int] = None
    top_posts: list[MetaTopPost] = []        # top 3 posts por reach (lifetime)
    # Pixel
    pixel_name: Optional[str] = None
    pixel_last_fired_at: Optional[datetime] = None
    pixel_days_idle: Optional[int] = None
    pixel_is_unavailable: Optional[bool] = None


class MetaPendingItem(BaseModel):
    """Item da checklist do que falta pra TI destravar."""
    key: str                                  # 'ig_basic', 'ads_auth', 'pixel_install', etc.
    label: str
    detail: str
    blocked_features: list[str] = []          # quais features ficam bloqueadas


class MetaDashboardResponse(BaseModel):
    has_connection: bool
    token_validated_at: Optional[datetime] = None
    business_name: Optional[str] = None
    instagram: MetaDashboardCard
    facebook: MetaDashboardCard
    pixel: MetaDashboardCard
    pending: list[MetaPendingItem] = []
