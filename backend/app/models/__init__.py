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
from app.models.core import (
    CoreBusiness,
    CoreUsersClinicorp,
    CoreProfessionals,
    CoreSpecialties,
    CoreProcedures,
    CoreAppointmentCategories,
    CoreAppointmentStatuses,
    CoreCrmCampaigns,
    CorePatients,
    CoreAppointments,
    CoreEstimates,
    CoreEstimateProcedures,
    CorePayments,
    CoreInvoices,
    CoreReceipts,
    CoreSummaryEntries,
)
from app.models.analytics import (
    DimPaciente, DimProfissional, DimTempo,
    FatoAgenda, FatoFinanceiro, FatoOrcamentos,
)
from app.models.sync_job import SyncJob
from app.models.sync_checkpoint import SyncCheckpoint
from app.models.contaazul_token import ContaAzulToken
from app.models.permission import Permission, RolePermission
from app.models.password_reset_token import PasswordResetToken

__all__ = [
    "Tenant", "User", "Role", "UserTenant",
    # Staging
    "StgCcBusiness", "StgCcUsers", "StgCcProfessionals",
    "StgCcSpecialties", "StgCcProcedures",
    "StgCcAppointmentCategories", "StgCcAppointmentStatuses",
    "StgCcCrmCampaigns", "StgCcAppointments", "StgCcEstimates",
    "StgCcPayments", "StgCcInvoices", "StgCcReceipts",
    "StgCcSummaryEntries", "StgCcKpisMonthly",
    # Core — cadastros
    "CoreBusiness", "CoreUsersClinicorp", "CoreProfessionals",
    "CoreSpecialties", "CoreProcedures",
    "CoreAppointmentCategories", "CoreAppointmentStatuses",
    "CoreCrmCampaigns", "CorePatients",
    # Core — eventos
    "CoreAppointments", "CoreEstimates", "CoreEstimateProcedures",
    "CorePayments", "CoreInvoices", "CoreReceipts", "CoreSummaryEntries",
    # Analytics — dimensões
    "DimTempo", "DimPaciente", "DimProfissional",
    # Analytics — fatos
    "FatoAgenda", "FatoOrcamentos", "FatoFinanceiro",
    # Sync control
    "SyncJob", "SyncCheckpoint", "ContaAzulToken",
    # Auth/RBAC
    "Permission", "RolePermission", "PasswordResetToken",
]
