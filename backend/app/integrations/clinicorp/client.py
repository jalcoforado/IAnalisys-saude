"""
Client HTTP para a API da Clinicorp.
Autenticação: Basic Auth (API_USER:API_TOKEN)
Parâmetros obrigatórios em toda request: subscriber_id, business_id
"""
import httpx
from typing import Any
from app.core.config import settings


class ClinicorpError(Exception):
    pass


class ClinicorpClient:
    def __init__(self) -> None:
        self._base_url = settings.CLINICORP_API_URL
        self._auth = (settings.CLINICORP_API_USER, settings.CLINICORP_API_TOKEN)
        self._base_params = {
            "subscriber_id": settings.CLINICORP_SUBSCRIBER_ID,
            "business_id": settings.CLINICORP_BUSINESS_ID,
        }

    async def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        all_params = {**self._base_params, **(params or {})}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{self._base_url}{endpoint}",
                params=all_params,
                auth=self._auth,
                headers={"Accept": "application/json"},
            )
        if response.status_code != 200:
            raise ClinicorpError(
                f"Clinicorp API error {response.status_code} on {endpoint}"
            )
        return response.json()

    # ── Negócio ──────────────────────────────────────────────

    async def get_business(self) -> Any:
        return await self._get("/business/list")

    # ── Analytics (agregados) ─────────────────────────────────

    async def get_analytics(self, from_date: str, to_date: str) -> Any:
        return await self._get("/analytics/list_results", {"from": from_date, "to": to_date})

    # ── Agendamentos ──────────────────────────────────────────

    async def get_appointments(self, from_date: str, to_date: str) -> Any:
        return await self._get("/appointment/list", {"from": from_date, "to": to_date})

    async def get_appointment_info(self, from_date: str, to_date: str) -> Any:
        return await self._get("/appointment/list_info", {"from": from_date, "to": to_date})

    # ── Orçamentos ────────────────────────────────────────────

    async def get_estimates(self, from_date: str, to_date: str) -> Any:
        return await self._get("/estimates/list", {"from": from_date, "to": to_date})

    # ── Financeiro ────────────────────────────────────────────

    async def get_cash_flow(self, from_date: str, to_date: str) -> Any:
        return await self._get("/financial/list_cash_flow", {"from": from_date, "to": to_date})

    async def get_financial_summary(self, from_date: str, to_date: str) -> Any:
        return await self._get("/financial/list_summary", {"from": from_date, "to": to_date})

    async def get_payments(self, from_date: str, to_date: str) -> Any:
        return await self._get("/financial/list_payments", {"from": from_date, "to": to_date})

    async def get_invoices(self, from_date: str, to_date: str) -> Any:
        return await self._get("/financial/list_invoices", {"from": from_date, "to": to_date})

    async def get_receipts(self, from_date: str, to_date: str) -> Any:
        return await self._get("/financial/list_receipt", {"from": from_date, "to": to_date})

    async def get_average_installments(self, from_date: str, to_date: str) -> Any:
        return await self._get("/financial/average_installments", {"from": from_date, "to": to_date})

    async def get_payment_list(self, from_date: str, to_date: str) -> Any:
        return await self._get("/payment/list", {"from": from_date, "to": to_date})

    # ── Vendas ────────────────────────────────────────────────

    async def get_expertise_revenue(self, from_date: str, to_date: str) -> Any:
        return await self._get("/sales/expertise_revenue", {"from": from_date, "to": to_date})

    async def get_estimates_conversion(self, from_date: str, to_date: str) -> Any:
        return await self._get("/sales/estimates_and_conversion", {"from": from_date, "to": to_date})

    # ── Operacional ───────────────────────────────────────────

    async def get_misses_goals(self, from_date: str, to_date: str) -> Any:
        return await self._get("/operational/list_misses_goals", {"from": from_date, "to": to_date})

    async def get_sales_goals(self, from_date: str, to_date: str) -> Any:
        return await self._get("/operational/list_sales_goals", {"from": from_date, "to": to_date})

    # ── CRM ───────────────────────────────────────────────────

    async def get_active_campaigns(self) -> Any:
        return await self._get("/crm/list_active_campaigns")
