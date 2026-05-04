"""
OAuth 2.0 Authorization Code flow para Conta Azul.

Endpoints:
  Auth:    https://auth.contaazul.com/login
  Token:   https://auth.contaazul.com/oauth2/token
  Scope:   openid profile aws.cognito.signin.user.admin

Token expira em 1 hora; renovação via refresh_token.

State carrega tenant_id codificado em base64-url ("<tenant_id>:<nonce>") para
amarrar o callback ao tenant correto sem precisar de query param extra.
"""
import base64
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx

from app.core.config import settings

_AUTH_URL = "https://auth.contaazul.com/login"
_TOKEN_URL = "https://auth.contaazul.com/oauth2/token"


class ContaAzulOAuthError(Exception):
    pass


def encode_state(tenant_id: str) -> str:
    """Empacota tenant_id + nonce no state (base64url, sem padding)."""
    nonce = secrets.token_hex(8)
    raw = f"{tenant_id}:{nonce}".encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def decode_state(state: str) -> str | None:
    """Extrai o tenant_id do state. Retorna None se o state não for válido."""
    if not state:
        return None
    try:
        padded = state + "=" * (-len(state) % 4)
        raw = base64.urlsafe_b64decode(padded.encode()).decode()
    except Exception:
        return None
    parts = raw.split(":", 1)
    if len(parts) != 2 or not parts[0]:
        return None
    return parts[0]


def build_authorization_url(state: str) -> str:
    """Gera a URL de autorização OAuth para redirecionar o usuário."""
    params = {
        "response_type": "code",
        "client_id": settings.CONTAAZUL_CLIENT_ID,
        "redirect_uri": settings.CONTAAZUL_REDIRECT_URI,
        "state": state,
        "scope": "openid profile aws.cognito.signin.user.admin",
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_token(code: str) -> dict:
    """
    Troca o authorization code por access_token + refresh_token.
    Retorna dict com: access_token, refresh_token, expires_at (datetime UTC).
    """
    creds = (settings.CONTAAZUL_CLIENT_ID, settings.CONTAAZUL_CLIENT_SECRET)
    # Conta Azul EXIGE client_id E client_secret no body, ALÉM da Basic auth.
    # Confirmado lendo o v1 PHP da Parente que funciona em produção desde mar/2026.
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            _TOKEN_URL,
            auth=creds,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.CONTAAZUL_REDIRECT_URI,
                "client_id": settings.CONTAAZUL_CLIENT_ID,
                "client_secret": settings.CONTAAZUL_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if resp.status_code != 200:
        raise ContaAzulOAuthError(
            f"Falha ao trocar código: HTTP {resp.status_code} — {resp.text[:200]}"
        )

    data = resp.json()
    if "access_token" not in data:
        raise ContaAzulOAuthError(f"access_token ausente na resposta: {data}")

    return _parse_token_response(data)


async def refresh_access_token(refresh_token: str) -> dict:
    """
    Renova o access_token usando o refresh_token.
    Retorna dict com: access_token, refresh_token, expires_at.
    """
    creds = (settings.CONTAAZUL_CLIENT_ID, settings.CONTAAZUL_CLIENT_SECRET)
    # Mesmo padrão do v1: Basic auth + client_id/secret no body.
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            _TOKEN_URL,
            auth=creds,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.CONTAAZUL_CLIENT_ID,
                "client_secret": settings.CONTAAZUL_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if resp.status_code != 200:
        raise ContaAzulOAuthError(
            f"Falha ao renovar token: HTTP {resp.status_code} — {resp.text[:200]}"
        )

    data = resp.json()
    if "access_token" not in data:
        raise ContaAzulOAuthError(f"access_token ausente na resposta de refresh: {data}")

    return _parse_token_response(data)


def _parse_token_response(data: dict) -> dict:
    expires_in = int(data.get("expires_in", 3600))
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=expires_in)
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "expires_at": expires_at,
    }
