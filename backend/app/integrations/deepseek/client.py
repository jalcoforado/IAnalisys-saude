"""
Client HTTP para a API da DeepSeek (compatível com OpenAI Chat Completions).

Endpoint: https://api.deepseek.com/v1/chat/completions
Auth: Bearer token no header.
Formato request/response: idêntico ao OpenAI Chat Completions API.

Convenção: método `complete_json()` força `response_format: {"type": "json_object"}`
pra DeepSeek devolver JSON estruturado parseável. Validar schema é
responsabilidade do caller (service).
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class DeepSeekError(Exception):
    """Erro genérico na chamada à DeepSeek. Detalhe vem em `args[0]`."""


# Mesma estratégia do Clinicorp: 4 tentativas com backoff exponencial em
# 429/5xx; outros 4xx falham imediatamente (bug de chamada não se resolve
# esperando).
_RETRY_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY = 1.5


class DeepSeekClient:
    """Wrapper assíncrono pra DeepSeek Chat Completions."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_url: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key or settings.DEEPSEEK_API_KEY
        self._api_url = (api_url or settings.DEEPSEEK_API_URL).rstrip("/")
        self._model = model or settings.DEEPSEEK_MODEL
        self._timeout = timeout

    @property
    def is_configured(self) -> bool:
        """Se False, caller deve aplicar fallback (heurística) sem tentar chamar."""
        return bool(self._api_key)

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int = 800,
    ) -> dict[str, Any]:
        """
        Chama DeepSeek e retorna o conteúdo da resposta parseado como JSON.

        Força `response_format: {"type": "json_object"}` — DeepSeek garante
        que o output será JSON válido. Se mesmo assim vier malformado,
        levanta DeepSeekError (caller cai pro fallback).
        """
        if not self.is_configured:
            raise DeepSeekError("DEEPSEEK_API_KEY não configurada — caller deve usar fallback.")

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        last_status: int | None = None
        last_body: str = ""

        for attempt in range(_RETRY_MAX_ATTEMPTS):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.post(
                        f"{self._api_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                last_status = response.status_code
                last_body = response.text[:500]

                # 4xx não-rate-limited: não adianta retentar
                if 400 <= response.status_code < 500 and response.status_code != 429:
                    raise DeepSeekError(
                        f"DeepSeek {response.status_code}: {last_body}"
                    )

                # 429 ou 5xx: backoff e tenta de novo
                if response.status_code >= 429:
                    if attempt < _RETRY_MAX_ATTEMPTS - 1:
                        delay = _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(-0.3, 0.3)
                        logger.warning(
                            "DeepSeek %s — retry em %.1fs (tentativa %d/%d)",
                            response.status_code, delay, attempt + 1, _RETRY_MAX_ATTEMPTS,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise DeepSeekError(
                        f"DeepSeek persistiu em {response.status_code} após {_RETRY_MAX_ATTEMPTS} tentativas"
                    )

                response.raise_for_status()
                body = response.json()
                content = body["choices"][0]["message"]["content"]

                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    raise DeepSeekError(
                        f"DeepSeek retornou JSON malformado: {e}; conteúdo: {content[:200]}"
                    ) from e

            except httpx.RequestError as e:
                if attempt < _RETRY_MAX_ATTEMPTS - 1:
                    delay = _RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning("DeepSeek erro de rede (%s) — retry em %.1fs", e, delay)
                    await asyncio.sleep(delay)
                    continue
                raise DeepSeekError(f"DeepSeek rede falhou após {_RETRY_MAX_ATTEMPTS} tentativas: {e}") from e

        # Defensivo — nunca deveria chegar aqui se a lógica acima estiver certa
        raise DeepSeekError(f"DeepSeek falhou silenciosamente; último status={last_status} body={last_body}")
