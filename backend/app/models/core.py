"""
Modelos da camada CORE — dados limpos, normalizados, com tipos coercidos.

Padrão:
- PK: id BIGINT autoincrement
- Idempotência: UNIQUE(tenant_id, external_id) onde external_id é a PK Clinicorp
- Sem FK rígida entre core_* (decisão arquitetural — integridade lógica via external_id)
- Soft delete: is_deleted BOOLEAN
- Timestamps locais: created_at / updated_at
- Timestamp da origem: external_updated_at (LastChange_Date / Modified / etc.)
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, func
)
from sqlalchemy.dialects.mysql import CHAR
from app.db.base import Base


# ── Mixin de colunas comuns ─────────────────────────────────────

def _id_col():
    return Column(BigInteger, primary_key=True, autoincrement=True)

def _tenant_col():
    return Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)

def _ext_id_col():
    return Column(String(64), nullable=False)

def _deleted_col():
    return Column(Boolean, nullable=False, default=False, server_default="0")

def _ext_updated_col():
    return Column(DateTime, nullable=True)

def _ts_cols():
    return (
        Column("created_at", DateTime, nullable=False,
               server_default=func.current_timestamp()),
        Column("updated_at", DateTime, nullable=False,
               server_default=func.current_timestamp(),
               onupdate=func.current_timestamp(),
               server_onupdate=func.current_timestamp()),
    )

def _uk(table_name: str):
    return UniqueConstraint("tenant_id", "external_id", name=f"uk_{table_name}_external")


# ── Cadastros ───────────────────────────────────────────────────

class CoreBusiness(Base):
    __tablename__ = "core_business"
    __table_args__ = (_uk("core_business"),)
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()
    name = Column(String(255), nullable=True)
    business_name = Column(String(255), nullable=True)
    company_id = Column(String(32), nullable=True)
    email = Column(String(255), nullable=True)


class CoreUsersClinicorp(Base):
    __tablename__ = "core_users_clinicorp"
    __table_args__ = (_uk("core_users_clinicorp"),)
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)


class CoreProfessionals(Base):
    __tablename__ = "core_professionals"
    __table_args__ = (_uk("core_professionals"),)
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()
    name = Column(String(255), nullable=True)
    cpf = Column(String(20), nullable=True)


class CoreSpecialties(Base):
    __tablename__ = "core_specialties"
    __table_args__ = (_uk("core_specialties"),)
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()
    description = Column(String(255), nullable=True)
    type = Column(String(50), nullable=True)
    language = Column(String(10), nullable=True)
    initial_id = Column(BigInteger, nullable=True)
    related_characteristic_id = Column(BigInteger, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")


class CoreProcedures(Base):
    __tablename__ = "core_procedures"
    __table_args__ = (
        _uk("core_procedures"),
        Index("ix_core_procedures_price_list", "tenant_id", "price_list_id"),
    )
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()
    internal_code = Column(String(50), nullable=True)
    procedure_name = Column(String(500), nullable=True)
    procedure_expertise_name = Column(String(255), nullable=True)
    type = Column(String(50), nullable=True)
    price_list_id = Column(BigInteger, nullable=True)
    price_list_name = Column(String(255), nullable=True)


class CoreAppointmentCategories(Base):
    __tablename__ = "core_appointment_categories"
    __table_args__ = (_uk("core_appointment_categories"),)
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()
    description = Column(String(255), nullable=True)
    color = Column(String(20), nullable=True)


class CoreAppointmentStatuses(Base):
    __tablename__ = "core_appointment_statuses"
    __table_args__ = (_uk("core_appointment_statuses"),)
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()
    description = Column(String(255), nullable=True)
    color = Column(String(20), nullable=True)
    type = Column(String(50), nullable=True)
    reference = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")


class CoreCrmCampaigns(Base):
    __tablename__ = "core_crm_campaigns"
    __table_args__ = (_uk("core_crm_campaigns"),)
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()
    name = Column(String(255), nullable=True)
    status = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)


# ── Derivado ────────────────────────────────────────────────────

class CorePatients(Base):
    __tablename__ = "core_patients"
    __table_args__ = (
        _uk("core_patients"),
        Index("ix_core_patients_last_seen", "tenant_id", "last_seen_at"),
    )
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()
    name = Column(String(255), nullable=True)
    mobile_phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    birth_date = Column(Date, nullable=True)
    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    total_appointments = Column(Integer, nullable=False, default=0, server_default="0")
    total_estimates = Column(Integer, nullable=False, default=0, server_default="0")
    total_payments = Column(Integer, nullable=False, default=0, server_default="0")
