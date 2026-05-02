# Importar todos os models aqui garante que o Alembic os descubra
# via app.db.base.Base.metadata
from app.models.tenant import Tenant
from app.models.user import User
from app.models.role import Role
from app.models.user_tenant import UserTenant
from app.models.staging import (
    StgCcBusiness,
    StgCcUsers,
    StgCcProfessionals,
    StgCcSpecialties,
    StgCcProcedures,
    StgCcAppointmentCategories,
    StgCcAppointmentStatuses,
    StgCcCrmCampaigns,
    StgCcAppointments,
    StgCcEstimates,
    StgCcPayments,
    StgCcInvoices,
    StgCcReceipts,
    StgCcSummaryEntries,
    StgCcKpisMonthly,
)
from app.models.sync_job import SyncJob
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.contaazul_token import ContaAzulToken

__all__ = [
    "Tenant", "User", "Role", "UserTenant",
    "StgCcBusiness", "StgCcUsers", "StgCcProfessionals",
    "StgCcSpecialties", "StgCcProcedures",
    "StgCcAppointmentCategories", "StgCcAppointmentStatuses",
    "StgCcCrmCampaigns", "StgCcAppointments", "StgCcEstimates",
    "StgCcPayments", "StgCcInvoices", "StgCcReceipts",
    "StgCcSummaryEntries", "StgCcKpisMonthly",
    "SyncJob", "SyncCheckpoint", "ContaAzulToken",
]
