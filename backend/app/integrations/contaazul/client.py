"""
Cliente HTTP para a API Conta Azul v2.
Usa Bearer token obtido via OAuth 2.0.

Documentação: https://developers.contaazul.com/
"""
from typing import Any

import httpx

_BASE_URL = "https://api.contaazul.com/v2"


class ContaAzulError(Exception):
    pass


class ContaAzulClient:
    def __init__(self, access_token: str) -> None:
        self._token = access_token
        self._headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

    async def _get(self, endpoint: str, params: dict | None = None) -> Any:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{_BASE_URL}{endpoint}",
                params=params or {},
                headers=self._headers,
            )
        if resp.status_code == 401:
            raise ContaAzulError("Token expirado ou inválido — reconecte a conta.")
        if resp.status_code != 200:
            raise ContaAzulError(
                f"Conta Azul API error {resp.status_code} em {endpoint}: {resp.text[:200]}"
            )
        return resp.json()

    # ── Financeiro ────────────────────────────────────────────

    async def get_accounts_receivable(
        self, due_date_from: str, due_date_to: str, page: int = 0, size: int = 100
    ) -> Any:
        """Contas a receber no período (por data de vencimento)."""
        return await self._get(
            "/accounts-receivable",
            {"dueDateFrom": due_date_from, "dueDateTo": due_date_to, "page": page, "size": size},
        )

    async def get_accounts_payable(
        self, due_date_from: str, due_date_to: str, page: int = 0, size: int = 100
    ) -> Any:
        """Contas a pagar no período."""
        return await self._get(
            "/accounts-payable",
            {"dueDateFrom": due_date_from, "dueDateTo": due_date_to, "page": page, "size": size},
        )

    async def get_financial_movements(
        self, start_date: str, end_date: str, page: int = 0, size: int = 100
    ) -> Any:
        """Lançamentos financeiros (movimentações de caixa/banco)."""
        return await self._get(
            "/financial-movements",
            {"startDate": start_date, "endDate": end_date, "page": page, "size": size},
        )

    # ── Vendas ────────────────────────────────────────────────

    async def get_sales(
        self, emission_start: str, emission_end: str, page: int = 0, size: int = 100
    ) -> Any:
        """Vendas/NFs emitidas no período."""
        return await self._get(
            "/sales",
            {"emissionStart": emission_start, "emissionEnd": emission_end, "page": page, "size": size},
        )

    # ── Clientes ──────────────────────────────────────────────

    async def get_customers(self, page: int = 0, size: int = 100) -> Any:
        """Lista de clientes cadastrados."""
        return await self._get("/customers", {"page": page, "size": size})

    # ── Empresa ───────────────────────────────────────────────

    async def get_company(self) -> Any:
        """Dados da empresa conectada."""
        return await self._get("/company")
