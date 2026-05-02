"""
Modelos de staging Clinicorp — record-level com idempotência por (tenant_id, external_id).

Schema uniforme:
- external_id: PK na origem (Clinicorp), VARCHAR(64) pra cobrir bigints + nomes
- external_updated_at: campo de delta quando disponível (LastChange_Date / Modified / z_LastChange_Date)
- raw_data: payload bruto da API (audit trail; útil para a IA explicar a origem do número)
- sync_job_id: rastreia qual execução trouxe o registro
- UNIQUE(tenant_id, external_id) garante upsert idempotente

São 15 tabelas: 8 estáticas + 6 transacionais + 1 agregada (kpis_monthly).
"""
from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey, Index, String, UniqueConstraint, func
)
from sqlalchemy.dialects.mysql import JSON, CHAR
from app.db.base import Base


def _staging_columns():
    """Colunas comuns a todas as tabelas stg_cc_*."""
    return [
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("tenant_id", CHAR(36), ForeignKey("tenants.id"), nullable=False),
        Column("external_id", String(64), nullable=False),
        Column("external_updated_at", DateTime, nullable=True),
        Column("raw_data", JSON, nullable=False),
        Column("synced_at", DateTime, nullable=False, server_default=func.current_timestamp()),
        Column("sync_job_id", BigInteger, ForeignKey("sync_jobs.id"), nullable=True),
    ]


def _staging_table_args(table_name: str):
    return (
        UniqueConstraint("tenant_id", "external_id", name=f"uk_{table_name}_external"),
        Index(f"ix_{table_name}_updated", "tenant_id", "external_updated_at"),
    )


# ── Estáticas (sem período) ────────────────────────────────────

class StgCcBusiness(Base):
    __tablename__ = "stg_cc_business"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCcUsers(Base):
    __tablename__ = "stg_cc_users"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCcProfessionals(Base):
    __tablename__ = "stg_cc_professionals"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCcSpecialties(Base):
    __tablename__ = "stg_cc_specialties"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCcProcedures(Base):
    __tablename__ = "stg_cc_procedures"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCcAppointmentCategories(Base):
    __tablename__ = "stg_cc_appointment_categories"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCcAppointmentStatuses(Base):
    __tablename__ = "stg_cc_appointment_statuses"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCcCrmCampaigns(Base):
    __tablename__ = "stg_cc_crm_campaigns"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


# ── Transacionais (por período) ───────────────────────────────

class StgCcAppointments(Base):
    __tablename__ = "stg_cc_appointments"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCcEstimates(Base):
    """raw_data contém ProcedureList[] nested — não normalizamos no staging."""
    __tablename__ = "stg_cc_estimates"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCcPayments(Base):
    __tablename__ = "stg_cc_payments"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCcInvoices(Base):
    __tablename__ = "stg_cc_invoices"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCcReceipts(Base):
    __tablename__ = "stg_cc_receipts"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


class StgCcSummaryEntries(Base):
    """Lançamentos contábeis de financial/list_summary.values[] (CREDIT/DEBIT)."""
    __tablename__ = "stg_cc_summary_entries"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()


# ── Agregada (1 linha por mês) ────────────────────────────────

class StgCcKpisMonthly(Base):
    """external_id = 'YYYY-MM-01'. raw_data = dict com payload de 10 endpoints agregados."""
    __tablename__ = "stg_cc_kpis_monthly"
    __table_args__ = _staging_table_args(__tablename__)
    id, tenant_id, external_id, external_updated_at, raw_data, synced_at, sync_job_id = _staging_columns()
