"""
Cliente HTTP mínimo para a Meta Graph API.

Sub-PR 21b — usado apenas para VALIDAR o token cadastrado pelo tenant:
  - GET /debug_token       → app_id, scopes, expires_at, is_valid
  - GET /me                → system_user info (id, name)
  - GET /me/accounts       → lista de Pages (id, name, access_token, ig_business_account)
  - GET /{business_id}     → business name + verification
  - GET /{pixel_id}        → pixel last_fired_time, name

Discovery rodada em /tmp/meta_discovery/ validou todos esses endpoints com o
token da Parente. Esse cliente é o mesmo que será expandido pelo sub-PR 21c
quando começarem os syncs reais.
"""
from typing import Any

import httpx

from app.core.config import settings


class MetaGraphError(Exception):
    """Erro genérico Graph API. `code` segue o `error.code` da Meta quando disponível."""

    def __init__(self, message: str, *, code: int | None = None, type_: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.type = type_


class MetaGraphClient:
    """Cliente assíncrono p/ Graph API. Token passado no construtor.

    Não armazena estado — instancie por request (igual ContaAzulClient).
    """

    def __init__(self, access_token: str, *, timeout: float = 20.0) -> None:
        self._token = access_token
        self._timeout = timeout
        self._base = settings.META_GRAPH_URL
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str, params: dict[str, Any] | None = None,
                   *, token_override: str | None = None) -> Any:
        client = self._get_client()
        p = dict(params or {})
        p["access_token"] = token_override or self._token
        resp = await client.get(f"{self._base}{path}", params=p)
        try:
            data = resp.json()
        except ValueError:
            raise MetaGraphError(f"Resposta não-JSON: HTTP {resp.status_code}")
        # Graph retorna 200 + `error` no body em vez de status != 2xx
        err = data.get("error") if isinstance(data, dict) else None
        if err:
            raise MetaGraphError(
                err.get("message", "Erro Meta Graph API"),
                code=err.get("code"),
                type_=err.get("type"),
            )
        return data

    # ------------------------------------------------------------
    # Endpoints usados na validação do token (sub-PR 21b)
    # ------------------------------------------------------------
    async def debug_token(self, token_to_check: str | None = None) -> dict[str, Any]:
        """Inspeciona o token (escopos, validade, app_id).

        Por padrão valida o próprio token do cliente. Para um Page Token,
        passe via `token_to_check`; o System User token é usado como bearer.
        """
        target = token_to_check or self._token
        return await self._get(
            "/debug_token",
            params={"input_token": target},
        )

    async def get_me(self) -> dict[str, Any]:
        """System User connecté (id, name)."""
        return await self._get("/me", params={"fields": "id,name"})

    async def get_my_pages(self) -> dict[str, Any]:
        """Lista pages associadas ao System User (com page token + IG vinculado)."""
        return await self._get(
            "/me/accounts",
            params={
                "fields": "id,name,access_token,instagram_business_account{id,username},category,fan_count",
            },
        )

    async def get_business(self, business_id: str) -> dict[str, Any]:
        return await self._get(
            f"/{business_id}",
            params={"fields": "id,name,verification_status,primary_page,timezone_id"},
        )

    async def get_ad_account(self, ad_account_id: str) -> dict[str, Any]:
        """Confere acesso à Ad Account. Falha com code 200 se não autorizada."""
        return await self._get(
            f"/{ad_account_id}",
            params={"fields": "id,name,account_status,currency,timezone_name,business"},
        )

    async def get_pixel(self, pixel_id: str) -> dict[str, Any]:
        return await self._get(
            f"/{pixel_id}",
            params={
                "fields": "id,name,creation_time,last_fired_time,owner_business,owner_ad_account,is_unavailable",
            },
        )

    async def get_ig_account(self, ig_account_id: str) -> dict[str, Any]:
        return await self._get(
            f"/{ig_account_id}",
            params={"fields": "id,username,name,followers_count,follows_count,media_count"},
        )

    # ------------------------------------------------------------
    # Endpoints de sync — Sub-PR 21c
    # ------------------------------------------------------------
    async def get_ig_profile_full(self, ig_account_id: str) -> dict[str, Any]:
        """Perfil IG completo p/ snapshot diário em stg_meta_ig_perfil."""
        return await self._get(
            f"/{ig_account_id}",
            params={
                "fields": (
                    "id,username,name,biography,followers_count,follows_count,"
                    "media_count,profile_picture_url,website"
                ),
            },
        )

    async def get_ig_media(self, ig_account_id: str, *, limit: int = 25) -> dict[str, Any]:
        """Lista de posts do IG (header — sem métricas detalhadas).

        Métricas/insights por post exigem `instagram_manage_insights` (App Review),
        então essa chamada só traz like_count/comments_count que vêm sem permission extra.
        """
        return await self._get(
            f"/{ig_account_id}/media",
            params={
                "fields": (
                    "id,caption,media_type,media_url,permalink,timestamp,"
                    "like_count,comments_count,thumbnail_url,is_comment_enabled"
                ),
                "limit": str(limit),
            },
        )

    async def get_fb_page_full(self, page_id: str, page_token: str) -> dict[str, Any]:
        """Detalhes da Page p/ snapshot em stg_meta_fb_page.

        Usa PAGE TOKEN (não o System User), pois alguns campos só vêm com page token.
        """
        return await self._get(
            f"/{page_id}",
            params={
                "fields": (
                    "id,name,username,category,about,description,"
                    "fan_count,followers_count,link,verification_status,"
                    "phone,emails,website,location,instagram_business_account"
                ),
            },
            token_override=page_token,
        )

    async def get_fb_posts(self, page_id: str, page_token: str, *, limit: int = 25) -> dict[str, Any]:
        """Posts publicados pela Page (header).

        likes.summary(true) e comments.summary(true) foram removidos porque exigem
        a permission Page Public Content Access (App Review) — engagement orgânico
        agora vem via /{post}/insights na transformação 21e.
        """
        return await self._get(
            f"/{page_id}/posts",
            params={
                "fields": (
                    "id,message,created_time,permalink_url,full_picture,shares"
                ),
                "limit": str(limit),
            },
            token_override=page_token,
        )

    # ------------------------------------------------------------
    # Insights — Sub-PR 21e
    # ------------------------------------------------------------
    async def get_ig_post_insights(
        self, post_id: str, metrics: list[str]
    ) -> dict[str, Any]:
        """Métricas por post IG (period=lifetime — cumulativo desde a publicação)."""
        return await self._get(
            f"/{post_id}/insights",
            params={"metric": ",".join(metrics)},
        )

    async def get_ig_post_comments(
        self, post_id: str, *, limit: int = 50,
    ) -> dict[str, Any]:
        """Comentários de um post IG (header — text, username, timestamp, likes)."""
        return await self._get(
            f"/{post_id}/comments",
            params={
                "fields": "id,text,username,timestamp,like_count,replies{id,text,username,timestamp}",
                "limit": str(limit),
            },
        )

    async def get_fb_post_insights(
        self, post_id: str, page_token: str, metrics: list[str]
    ) -> dict[str, Any]:
        """Métricas por post FB (period=lifetime). Usa Page Token."""
        return await self._get(
            f"/{post_id}/insights",
            params={"metric": ",".join(metrics)},
            token_override=page_token,
        )

    async def get_ig_account_insights_daily(
        self, ig_account_id: str, metrics: list[str], *, since_epoch: int, until_epoch: int
    ) -> dict[str, Any]:
        """Métricas da conta IG por dia (since/until em epoch)."""
        return await self._get(
            f"/{ig_account_id}/insights",
            params={
                "metric": ",".join(metrics),
                "period": "day",
                "since": str(since_epoch),
                "until": str(until_epoch),
            },
        )

    async def get_fb_page_insights_daily(
        self, page_id: str, page_token: str, metrics: list[str],
        *, since_epoch: int, until_epoch: int,
    ) -> dict[str, Any]:
        """Métricas da Page FB por dia (since/until em epoch). Usa Page Token."""
        return await self._get(
            f"/{page_id}/insights",
            params={
                "metric": ",".join(metrics),
                "period": "day",
                "since": str(since_epoch),
                "until": str(until_epoch),
            },
            token_override=page_token,
        )

    async def get_pixel_full(self, pixel_id: str) -> dict[str, Any]:
        """Detalhes do Pixel p/ snapshot em stg_meta_pixel."""
        return await self._get(
            f"/{pixel_id}",
            params={
                "fields": (
                    "id,name,creation_time,last_fired_time,owner_business,"
                    "owner_ad_account,is_unavailable"
                ),
            },
        )
