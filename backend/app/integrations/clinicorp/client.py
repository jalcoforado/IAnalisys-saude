"""
Client HTTP para a API da Clinicorp.

Autenticação: Basic Auth (API_USER:API_TOKEN)
Parâmetros obrigatórios em toda request: subscriber_id, business_id

Convenção: todos os métodos retornam JSON cru. Cabe ao sync_service
extrair listas, normalizar PKs e fazer upsert em staging.
"""
import asyncio
import random

import httpx
from typing import Any
from app.core.config import settings


class ClinicorpError(Exception):
    pass


# Retry: total de 1 tentativa inicial + N retries em 429/5xx
_RETRY_MAX_ATTEMPTS = 4
# Backoff exponencial em segundos: 2, 4, 8, 16 (com jitter ±0.5s)
_RETRY_BASE_DELAY = 2.0


class ClinicorpClient:
    def __init__(self) -> None:
        self._base_url = settings.CLINICORP_API_URL
        self._auth = (settings.CLINICORP_API_USER, settings.CLINICORP_API_TOKEN)
        self._base_params = {
            "subscriber_id": settings.CLINICORP_SUBSCRIBER_ID,
            "business_id": settings.CLINICORP_BUSINESS_ID,
        }

    async def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """GET com retry exponencial em 429 (rate limit) e 5xx (transientes).
        Outros 4xx falham imediatamente — bug de chamada não se resolve esperando.
        """
        all_params = {**self._base_params, **(params or {})}
        last_status: int | None = None
        last_text: str = ""
        for attempt in range(_RETRY_MAX_ATTEMPTS):
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(
                    f"{self._base_url}{endpoint}",
                    params=all_params,
                    auth=self._auth,
                    headers={"Accept": "application/json"},
                )
            if response.status_code == 200:
                return response.json()
            last_status = response.status_code
            last_text = response.text[:200]
            transient = response.status_code == 429 or 500 <= response.status_code < 600
            if not transient:
                raise ClinicorpError(
                    f"Clinicorp {response.status_code} on {endpoint}: {last_text}"
                )
            if attempt >= _RETRY_MAX_ATTEMPTS - 1:
                break
            delay = _RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(-0.5, 0.5)
            await asyncio.sleep(max(0.1, delay))
        raise ClinicorpError(
            f"Clinicorp {last_status} on {endpoint} (após {_RETRY_MAX_ATTEMPTS} tentativas): {last_text}"
        )

    # ── Cadastros estáticos (sem período) ─────────────────────

    async def list_business(self) -> Any:
        return await self._get("/business/list")

    async def list_users(self) -> Any:
        return await self._get("/security/list_users")

    async def list_professionals(self) -> Any:
        return await self._get("/professional/list_all_professionals")

    async def list_specialties(self) -> Any:
        return await self._get("/procedures/list_specialties")

    async def list_procedures(self) -> Any:
        return await self._get("/procedures/list")

    async def list_appointment_categories(self) -> Any:
        return await self._get("/appointment/list_categories")

    async def list_appointment_statuses(self) -> Any:
        return await self._get("/appointment/status_list")

    async def list_chairs(self) -> Any:
        return await self._get("/business/list_chairs")

    async def list_active_campaigns(self) -> Any:
        return await self._get("/crm/list_active_campaigns")

    # ── Pacientes individuais ─────────────────────────────────
    # Não há /patient/list — só busca individual por PatientId.
    # Usado pelo enriquecimento que traz BirthDate, Email, Phone, CPF, Status.

    async def get_patient(self, patient_id: int) -> Any:
        return await self._get("/patient/get", {"PatientId": patient_id})

    # ── Transacionais (por período) ───────────────────────────

    async def list_appointments(self, from_date: str, to_date: str) -> Any:
        return await self._get("/appointment/list", {"from": from_date, "to": to_date})

    async def list_estimates(self, from_date: str, to_date: str) -> Any:
        return await self._get("/estimates/list", {"from": from_date, "to": to_date})

    async def list_payments(self, from_date: str, to_date: str) -> Any:
        return await self._get(
            "/payment/list",
            {"from": from_date, "to": to_date, "include_total_amount": "X"},
        )

    async def list_invoices(self, from_date: str, to_date: str) -> Any:
        return await self._get("/financial/list_invoices", {"from": from_date, "to": to_date})

    async def list_receipts(self, from_date: str, to_date: str) -> Any:
        return await self._get("/financial/list_receipt", {"from": from_date, "to": to_date})

    async def list_summary(self, from_date: str, to_date: str) -> Any:
        return await self._get("/financial/list_summary", {"from": from_date, "to": to_date})

    # ── Agregados (para kpis_monthly) ─────────────────────────

    async def list_cash_flow(self, from_date: str, to_date: str) -> Any:
        return await self._get("/financial/list_cash_flow", {"from": from_date, "to": to_date})

    async def list_payments_aggregated(self, from_date: str, to_date: str) -> Any:
        return await self._get("/financial/list_payments", {"from": from_date, "to": to_date})

    async def average_installments(self, from_date: str, to_date: str) -> Any:
        return await self._get("/financial/average_installments", {"from": from_date, "to": to_date})

    async def list_appointment_info(self, from_date: str, to_date: str) -> Any:
        return await self._get("/appointment/list_info", {"from": from_date, "to": to_date})

    async def list_estimates_conversion(self, from_date: str, to_date: str) -> Any:
        return await self._get("/sales/estimates_and_conversion", {"from": from_date, "to": to_date})

    async def list_expertise_revenue(self, from_date: str, to_date: str) -> Any:
        return await self._get("/sales/expertise_revenue", {"from": from_date, "to": to_date})

    async def list_patient_estimates(self, from_date: str, to_date: str) -> Any:
        return await self._get("/patient/list_estimates", {"from": from_date, "to": to_date})

    async def list_misses_goals(self, from_date: str, to_date: str) -> Any:
        return await self._get("/operational/list_misses_goals", {"from": from_date, "to": to_date})

    async def list_sales_goals(self, from_date: str, to_date: str) -> Any:
        return await self._get("/operational/list_sales_goals", {"from": from_date, "to": to_date})

    async def list_analytics(self, from_date: str, to_date: str) -> Any:
        return await self._get("/analytics/list_results", {"from": from_date, "to": to_date})
