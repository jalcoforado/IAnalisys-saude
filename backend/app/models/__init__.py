# Importar todos os models aqui garante que o Alembic os descubra
# via app.db.base.Base.metadata
from app.models.tenant import Tenant
from app.models.user import User
from app.models.role import Role
from app.models.user_tenant import UserTenant
from app.models.staging import (
    StgAppointment,
    StgEstimate,
    StgCashFlow,
    StgPayment,
    StgAnalytics,
    StgFinancialSummary,
    StgEstimatesConversion,
)
from app.models.sync_job import SyncJob
from app.models.contaazul_token import ContaAzulToken

__all__ = [
    "Tenant", "User", "Role", "UserTenant",
    "StgAppointment", "StgEstimate", "StgCashFlow",
    "StgPayment", "StgAnalytics", "StgFinancialSummary",
    "StgEstimatesConversion", "SyncJob", "ContaAzulToken",
]
