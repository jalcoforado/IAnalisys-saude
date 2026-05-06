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
    Numeric, String, Text, UniqueConstraint, func
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


class CoreAppointmentTags(Base):
    """Tags (AppointmentMarker) aplicadas a appointments no Clinicorp.
    Workflow operacional do gestor: "Aguardado vaga", "Encaixe", "REMARCAR",
    "FINANCEIRO CONFERIDO", "CRC ORÇAMENTO - contatar", etc.
    Cada tag tem id global próprio (external_id). Um appointment pode ter N tags.
    """
    __tablename__ = "core_appointment_tags"
    __table_args__ = (
        _uk("core_appointment_tags"),
        Index("ix_core_appointment_tags_appointment", "tenant_id", "appointment_external_id"),
        Index("ix_core_appointment_tags_class", "tenant_id", "tag_class"),
    )
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    appointment_external_id = Column(String(64), nullable=False)
    name = Column(String(255), nullable=True)
    color = Column(String(20), nullable=True)
    type = Column(String(50), nullable=True)
    template_id = Column(String(64), nullable=True)
    tag_class = Column(String(20), nullable=True)
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()


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
        Index("ix_core_patients_cpf", "tenant_id", "cpf"),
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
    cpf = Column(String(14), nullable=True)
    status = Column(String(20), nullable=True)
    gender = Column(String(1), nullable=True)  # 'M' | 'F' | NULL
    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    total_appointments = Column(Integer, nullable=False, default=0, server_default="0")
    total_estimates = Column(Integer, nullable=False, default=0, server_default="0")
    total_payments = Column(Integer, nullable=False, default=0, server_default="0")


# ── Eventos ─────────────────────────────────────────────────────

class CoreAppointments(Base):
    __tablename__ = "core_appointments"
    __table_args__ = (
        _uk("core_appointments"),
        Index("ix_core_appointments_date", "tenant_id", "appointment_date"),
        Index("ix_core_appointments_professional", "tenant_id", "professional_external_id"),
        Index("ix_core_appointments_patient", "tenant_id", "patient_external_id"),
    )
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()
    patient_external_id = Column(BigInteger, nullable=True)
    patient_name = Column(String(255), nullable=True)
    patient_email = Column(String(255), nullable=True)
    patient_mobile_phone = Column(String(50), nullable=True)
    professional_external_id = Column(BigInteger, nullable=True)
    business_external_id = Column(BigInteger, nullable=True)
    appointment_date = Column(DateTime, nullable=True)
    from_time = Column(String(5), nullable=True)
    to_time = Column(String(5), nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    category_id = Column(BigInteger, nullable=True)
    category_description = Column(String(255), nullable=True)
    category_color = Column(String(20), nullable=True)
    status_id = Column(BigInteger, nullable=True)
    procedures_text = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    alert_info = Column(Text, nullable=True)
    schedule_to_id = Column(BigInteger, nullable=True)
    was_edited = Column(Boolean, nullable=False, default=False, server_default="0")
    created_external_at = Column(DateTime, nullable=True)
    created_external_user_id = Column(BigInteger, nullable=True)
    created_external_user_name = Column(String(255), nullable=True)


class CoreEstimates(Base):
    __tablename__ = "core_estimates"
    __table_args__ = (
        _uk("core_estimates"),
        Index("ix_core_estimates_date", "tenant_id", "estimate_date"),
        Index("ix_core_estimates_patient", "tenant_id", "patient_external_id"),
    )
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()
    patient_external_id = Column(BigInteger, nullable=True)
    patient_name = Column(String(255), nullable=True)
    patient_mobile_phone = Column(String(50), nullable=True)
    professional_external_id = Column(BigInteger, nullable=True)
    professional_name = Column(String(255), nullable=True)
    business_external_id = Column(BigInteger, nullable=True)
    amount = Column(Numeric(12, 2), nullable=True)
    status = Column(String(50), nullable=True)
    estimate_date = Column(DateTime, nullable=True)
    search_date = Column(DateTime, nullable=True)
    created_external_at = Column(DateTime, nullable=True)
    procedures_count = Column(Integer, nullable=False, default=0, server_default="0")


class CoreEstimateProcedures(Base):
    __tablename__ = "core_estimate_procedures"
    __table_args__ = (
        _uk("core_estimate_procedures"),
        Index("ix_core_estimate_procedures_treatment", "tenant_id", "treatment_external_id"),
        Index("ix_core_estimate_procedures_patient", "tenant_id", "patient_external_id"),
    )
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()
    treatment_external_id = Column(BigInteger, nullable=True)
    patient_external_id = Column(BigInteger, nullable=True)
    dentist_external_id = Column(BigInteger, nullable=True)
    dentist_name = Column(String(255), nullable=True)
    operation_description = Column(Text, nullable=True)
    specialty_id = Column(BigInteger, nullable=True)
    procedure_characteristic_id = Column(BigInteger, nullable=True)
    related_characteristic_id = Column(BigInteger, nullable=True)
    amount = Column(Numeric(12, 2), nullable=True)
    final_amount = Column(Numeric(12, 2), nullable=True)
    original_amount = Column(Numeric(12, 2), nullable=True)
    minimum_procedure_amount = Column(Numeric(12, 2), nullable=True)
    bill_type = Column(String(50), nullable=True)
    sequence = Column(Integer, nullable=True)
    tooth = Column(String(50), nullable=True)
    surface = Column(String(50), nullable=True)
    executed = Column(Boolean, nullable=False, default=False, server_default="0")
    payment_accounted = Column(Boolean, nullable=False, default=False, server_default="0")
    payment_plan_id = Column(BigInteger, nullable=True)
    price_id = Column(BigInteger, nullable=True)
    price_list_id = Column(BigInteger, nullable=True)
    status_id = Column(BigInteger, nullable=True)
    status_description = Column(String(255), nullable=True)
    created_external_at = Column(DateTime, nullable=True)


class CorePayments(Base):
    __tablename__ = "core_payments"
    __table_args__ = (
        _uk("core_payments"),
        Index("ix_core_payments_payment_date", "tenant_id", "payment_date"),
        Index("ix_core_payments_patient", "tenant_id", "patient_external_id"),
    )
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()
    payment_header_external_id = Column(BigInteger, nullable=True)
    treatment_external_id = Column(BigInteger, nullable=True)
    patient_external_id = Column(BigInteger, nullable=True)
    patient_name = Column(String(255), nullable=True)
    payer_name = Column(String(255), nullable=True)
    payer_email = Column(String(255), nullable=True)
    payer_phone = Column(String(50), nullable=True)
    payer_document = Column(String(20), nullable=True)
    amount = Column(Numeric(12, 2), nullable=True)
    service_amount = Column(Numeric(12, 2), nullable=True)
    total_amount = Column(Numeric(12, 2), nullable=True)
    fee = Column(Numeric(12, 2), nullable=True)
    interest_fee = Column(Numeric(12, 2), nullable=True)
    penalty_fee = Column(Numeric(12, 2), nullable=True)
    type = Column(String(50), nullable=True)
    payment_form = Column(String(50), nullable=True)
    payment_form_characteristic_id = Column(BigInteger, nullable=True)
    installment_number = Column(Integer, nullable=True)
    installments_count = Column(Integer, nullable=True)
    person_type = Column(String(50), nullable=True)
    payment_description = Column(Text, nullable=True)
    receiver_business_external_id = Column(BigInteger, nullable=True)
    is_received = Column(Boolean, nullable=False, default=False, server_default="0")
    is_confirmed = Column(Boolean, nullable=False, default=False, server_default="0")
    is_canceled = Column(Boolean, nullable=False, default=False, server_default="0")
    payment_date = Column(DateTime, nullable=True)
    received_date = Column(DateTime, nullable=True)
    confirmed_date = Column(DateTime, nullable=True)
    check_out_date = Column(DateTime, nullable=True)
    post_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    transaction_external_id = Column(String(128), nullable=True)


class CoreInvoices(Base):
    __tablename__ = "core_invoices"
    __table_args__ = (
        _uk("core_invoices"),
        Index("ix_core_invoices_date", "tenant_id", "invoice_date"),
    )
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()
    reference_id = Column(BigInteger, nullable=True)
    amount = Column(Numeric(12, 2), nullable=True)
    description = Column(Text, nullable=True)
    patient_external_id = Column(BigInteger, nullable=True)
    patient_name = Column(String(255), nullable=True)
    invoice_date = Column(DateTime, nullable=True)
    type = Column(String(50), nullable=True)
    status = Column(String(50), nullable=True)
    is_received = Column(Boolean, nullable=False, default=False, server_default="0")
    is_confirmed = Column(Boolean, nullable=False, default=False, server_default="0")
    installment_number = Column(Integer, nullable=True)
    receiver_business_external_id = Column(BigInteger, nullable=True)
    url = Column(String(500), nullable=True)


class CoreReceipts(Base):
    __tablename__ = "core_receipts"
    __table_args__ = (
        _uk("core_receipts"),
        Index("ix_core_receipts_date", "tenant_id", "receipt_date"),
    )
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()
    reference_id = Column(BigInteger, nullable=True)
    amount = Column(Numeric(12, 2), nullable=True)
    description = Column(Text, nullable=True)
    patient_external_id = Column(BigInteger, nullable=True)
    patient_name = Column(String(255), nullable=True)
    receipt_date = Column(DateTime, nullable=True)
    receiver_business_external_id = Column(BigInteger, nullable=True)


class CoreSummaryEntries(Base):
    __tablename__ = "core_summary_entries"
    __table_args__ = (
        _uk("core_summary_entries"),
        Index("ix_core_summary_entries_date", "tenant_id", "entry_date"),
        Index("ix_core_summary_entries_period", "tenant_id", "year", "month"),
        Index("ix_core_summary_entries_type", "tenant_id", "type"),
    )
    id = _id_col()
    tenant_id = _tenant_col()
    external_id = _ext_id_col()
    is_deleted = _deleted_col()
    external_updated_at = _ext_updated_col()
    created_at, updated_at = _ts_cols()
    year = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    entry_date = Column(DateTime, nullable=True)
    post_date = Column(DateTime, nullable=True)
    account_id = Column(BigInteger, nullable=True)
    type = Column(String(20), nullable=True)
    post_type = Column(String(50), nullable=True)
    entry_type = Column(String(50), nullable=True)
    related_book_entry_id = Column(BigInteger, nullable=True)
    related_person_id = Column(BigInteger, nullable=True)
    related_business_id = Column(BigInteger, nullable=True)
    business_external_id = Column(BigInteger, nullable=True)
    business_name = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    reference_entity = Column(String(50), nullable=True)
    reference_id_text = Column(String(255), nullable=True)
    additional_info = Column(Text, nullable=True)
    is_open = Column(Boolean, nullable=False, default=False, server_default="0")
    is_automated = Column(Boolean, nullable=False, default=False, server_default="0")
    is_manual = Column(Boolean, nullable=False, default=False, server_default="0")
    person_id = Column(BigInteger, nullable=True)
    amount = Column(Numeric(12, 2), nullable=True)
    amount_before_discounts = Column(Numeric(12, 2), nullable=True)
    payment_form_characteristic_id = Column(BigInteger, nullable=True)
