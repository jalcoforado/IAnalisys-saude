"""
Cliente HTTP para a API Conta Azul.

Endpoints validados em produção (smoke-test 2026-05-04, doc em
`reference_contaazul_v1.md`):

  - GET /v1/pessoas
  - GET /v1/produtos
  - GET /v1/servico                                       (singular!)
  - GET /v1/venda/vendedores                              (array puro)
  - GET /v1/financeiro/eventos-financeiros/contas-a-receber/buscar
  - GET /v1/financeiro/eventos-financeiros/contas-a-pagar/buscar

🔥 PEGADINHA CRÍTICA: o gateway exige Content-Type+Accept JSON em TODA
request, mesmo GET. Sem isso retorna 401 "Invalid token: policy(JWT-VERIFY)"
mesmo com token válido.

Convenção de wrapper inconsistente entre endpoints:
  - pessoas/produtos:  {"totalItems": N, "items": [...]}
  - servicos/eventos:  {"itens_totais": N, "itens": [...], "totais": {...}}
  - vendedores:        [...] (array puro)
"""
from datetime import date
from typing import Any

import httpx


_BASE_URL = "https://api-v2.contaazul.com"

# Sem esses dois cabeçalhos a API retorna 401 — confirmar antes de mexer.
_REQUIRED_JSON_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}


class ContaAzulError(Exception):
    pass


class ContaAzulClient:
    def __init__(self, access_token: str, *, timeout: float = 20.0) -> None:
        self._token = access_token
        self._timeout = timeout
        self._headers = {
            **_REQUIRED_JSON_HEADERS,
            "Authorization": f"Bearer {access_token}",
        }

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                f"{_BASE_URL}{path}",
                params=params or {},
                headers=self._headers,
            )

        if resp.status_code == 401:
            raise ContaAzulError(
                "Token expirado ou inválido — reconecte ou renove via /contaazul/refresh."
            )
        if resp.status_code == 429:
            raise ContaAzulError(
                "Rate limit do Conta Azul atingido. Espere alguns minutos e tente novamente. "
                "(API costuma renovar quota a cada hora.)"
            )
        if resp.status_code >= 400:
            raise ContaAzulError(
                f"Conta Azul API error {resp.status_code} em {path}: {resp.text[:240]}"
            )
        return resp.json()

    # ── Pessoas (clientes + fornecedores) ─────────────────────

    async def list_pessoas(
        self,
        *,
        tamanho_pagina: int = 200,
        offset: int = 0,
        nome: str | None = None,
        ativo: bool | None = None,
    ) -> dict:
        """Lista pessoas (clientes + fornecedores em uma só chamada).

        Retorno: {"totalItems": int, "items": [...]}.
        Cada item: id, nome, documento, email, telefone, ativo, perfis (array),
        tipo_pessoa ("Física"|"Jurídica"), id_legado, uuid_legado, datas.
        """
        params: dict[str, Any] = {"tamanho_pagina": tamanho_pagina, "offset": offset}
        if nome:
            params["nome"] = nome
        if ativo is not None:
            params["ativo"] = "true" if ativo else "false"
        return await self._get("/v1/pessoas", params)

    async def get_pessoa(self, pessoa_id: str) -> dict:
        """Detalhe completo de uma pessoa (com endereço etc.)."""
        return await self._get(f"/v1/pessoas/{pessoa_id}")

    # ── Produtos ──────────────────────────────────────────────

    async def list_produtos(
        self,
        *,
        tamanho_pagina: int = 200,
        offset: int = 0,
        status: str | None = None,
    ) -> dict:
        """Retorno: {"totalItems": int, "items": [...]}.
        Item: id, nome, codigo, tipo (PRODUCT|SERVICE), status, saldo,
        valor_venda, custo_medio, nivel_estoque, ean, etc.
        """
        params: dict[str, Any] = {"tamanho_pagina": tamanho_pagina, "offset": offset}
        if status:
            params["status"] = status
        return await self._get("/v1/produtos", params)

    # ── Serviços ──────────────────────────────────────────────

    async def list_servicos(self) -> dict:
        """Lista serviços odontológicos (sem paginação aparente).

        Retorno: {"itens_totais": int, "itens": [...]}.
        Item: id, id_servico, codigo, descricao, nome, preco, custo,
        status, tipo_servico (PRESTADO|CONTRATADO).
        """
        return await self._get("/v1/servico")

    # ── Vendedores ────────────────────────────────────────────

    async def list_vendedores(self) -> list[dict]:
        """Lista vendedores. ATENÇÃO: resposta é array puro, sem wrapper."""
        return await self._get("/v1/venda/vendedores")

    # ── Financeiro ────────────────────────────────────────────

    async def list_contas_receber(
        self,
        *,
        data_vencimento_de: date | str,
        data_vencimento_ate: date | str,
        tamanho_pagina: int = 200,
        status: str | None = None,
    ) -> dict:
        """Contas a receber no período (por data de vencimento).

        Retorno: {"itens_totais", "itens": [...], "totais": {...}}.
        Item tem `cliente` (não fornecedor) e `renegociacao`.
        Status: OVERDUE | PENDING | ACQUITTED | DUE_TODAY.
        """
        params: dict[str, Any] = {
            "data_vencimento_de": _date_str(data_vencimento_de),
            "data_vencimento_ate": _date_str(data_vencimento_ate),
            "tamanho_pagina": tamanho_pagina,
        }
        if status:
            params["status"] = status
        return await self._get(
            "/v1/financeiro/eventos-financeiros/contas-a-receber/buscar",
            params,
        )

    async def list_contas_pagar(
        self,
        *,
        data_vencimento_de: date | str,
        data_vencimento_ate: date | str,
        tamanho_pagina: int = 200,
        status: str | None = None,
    ) -> dict:
        """Contas a pagar no período. Mesma estrutura de receber, mas com
        `fornecedor` no lugar de `cliente` e sem `renegociacao`.
        """
        params: dict[str, Any] = {
            "data_vencimento_de": _date_str(data_vencimento_de),
            "data_vencimento_ate": _date_str(data_vencimento_ate),
            "tamanho_pagina": tamanho_pagina,
        }
        if status:
            params["status"] = status
        return await self._get(
            "/v1/financeiro/eventos-financeiros/contas-a-pagar/buscar",
            params,
        )


def _date_str(d: date | str) -> str:
    return d.isoformat() if isinstance(d, date) else d
