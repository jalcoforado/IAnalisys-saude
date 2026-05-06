"""
Modelos da camada ANALYTICS — dimensões e fatos para dashboards e IA.

dim_*  → entidades pré-formatadas para JOINs (calendário, paciente, profissional)
fato_* → eventos quantitativos com FK lógica para dimensões
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Index, Integer,
    Numeric, String, UniqueConstraint, func
)
from sqlalchemy.dialects.mysql import CHAR
from app.db.base import Base


class DimTempo(Base):
    """
    Dimensão de calendário. 1 linha por dia, populada proceduralmente.
    Não tem tenant_id (calendário é universal).
    """
    __tablename__ = "dim_tempo"
    __table_args__ = (
        Index("ix_dim_tempo_year_month", "year", "month"),
        Index("ix_dim_tempo_year_month_key", "year_month_key"),
        Index("ix_dim_tempo_year_quarter_key", "year_quarter_key"),
    )

    date_key = Column(Date, primary_key=True)
    year = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    day = Column(Integer, nullable=False)
    week = Column(Integer, nullable=False)
    day_of_week = Column(Integer, nullable=False)   # 1=dom .. 7=sáb (DAYOFWEEK MySQL)
    day_of_year = Column(Integer, nullable=False)
    year_month_key = Column(String(7), nullable=False)        # 'YYYY-MM'
    year_quarter_key = Column(String(7), nullable=False)      # 'YYYY-Q1'
    is_weekend = Column(Boolean, nullable=False)
    month_name_pt = Column(String(20), nullable=False)
    day_of_week_name_pt = Column(String(20), nullable=False)


class DimPaciente(Base):
    """Materialização de core_patients com colunas calculadas (is_active, days_since_last_seen)."""
    __tablename__ = "dim_paciente"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_dim_paciente_external"),
        Index("ix_dim_paciente_active", "tenant_id", "is_active"),
        Index("ix_dim_paciente_last_seen", "tenant_id", "last_seen_at"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    external_id = Column(String(64), nullable=False)
    name = Column(String(255), nullable=True)
    mobile_phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    birth_date = Column(Date, nullable=True)
    cpf = Column(String(14), nullable=True)
    gender = Column(String(1), nullable=True)
    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    days_since_last_seen = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=False, server_default="0")
    total_appointments = Column(Integer, nullable=False, default=0, server_default="0")
    total_estimates = Column(Integer, nullable=False, default=0, server_default="0")
    total_payments = Column(Integer, nullable=False, default=0, server_default="0")
    rebuilt_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())


class DimProfissional(Base):
    """Espelho de core_professionals para uso em dashboards."""
    __tablename__ = "dim_profissional"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_dim_profissional_external"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    external_id = Column(String(64), nullable=False)
    name = Column(String(255), nullable=True)
    cpf = Column(String(20), nullable=True)
    rebuilt_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())


# ── Fatos ───────────────────────────────────────────────────────

class FatoAgenda(Base):
    """1 linha por agendamento. Métricas: absenteísmo, consultas/período."""
    __tablename__ = "fato_agenda"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_fato_agenda_external"),
        Index("ix_fato_agenda_date", "tenant_id", "date_key"),
        Index("ix_fato_agenda_year_month", "tenant_id", "year_month_key"),
        Index("ix_fato_agenda_patient", "tenant_id", "patient_external_id"),
        Index("ix_fato_agenda_professional", "tenant_id", "professional_external_id"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    external_id = Column(String(64), nullable=False)
    date_key = Column(Date, nullable=True)
    year = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    year_month_key = Column(String(7), nullable=True)
    rebuilt_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    patient_external_id = Column(BigInteger, nullable=True)
    professional_external_id = Column(BigInteger, nullable=True)
    appointment_datetime = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    is_canceled = Column(Boolean, nullable=False, default=False, server_default="0")
    category_description = Column(String(255), nullable=True)
    category_color = Column(String(20), nullable=True)
    category_group = Column(String(20), nullable=True)  # consulta|retorno|manutencao|...
    status_id = Column(BigInteger, nullable=True)
    status_type = Column(String(50), nullable=True)
    status_description = Column(String(100), nullable=True)
    status_color = Column(String(20), nullable=True)
    # Flags desnormalizadas das tags do Clinicorp para agregação rápida
    has_waitlist = Column(Boolean, nullable=False, default=False, server_default="0")
    has_encaixe = Column(Boolean, nullable=False, default=False, server_default="0")
    has_remarcar = Column(Boolean, nullable=False, default=False, server_default="0")
    has_lembrete = Column(Boolean, nullable=False, default=False, server_default="0")
    has_orcamento_pendente = Column(Boolean, nullable=False, default=False, server_default="0")
    has_retorno_pendente = Column(Boolean, nullable=False, default=False, server_default="0")
    has_financeiro_conferido = Column(Boolean, nullable=False, default=False, server_default="0")


class FatoOrcamentos(Base):
    """1 linha por orçamento (header). Métricas: conversão, ticket médio."""
    __tablename__ = "fato_orcamentos"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_fato_orcamentos_external"),
        Index("ix_fato_orcamentos_date", "tenant_id", "date_key"),
        Index("ix_fato_orcamentos_year_month", "tenant_id", "year_month_key"),
        Index("ix_fato_orcamentos_status", "tenant_id", "status"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    external_id = Column(String(64), nullable=False)
    date_key = Column(Date, nullable=True)
    year = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    year_month_key = Column(String(7), nullable=True)
    rebuilt_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    patient_external_id = Column(BigInteger, nullable=True)
    professional_external_id = Column(BigInteger, nullable=True)
    amount = Column(Numeric(12, 2), nullable=True)
    status = Column(String(50), nullable=True)
    is_approved = Column(Boolean, nullable=False, default=False, server_default="0")
    is_rejected = Column(Boolean, nullable=False, default=False, server_default="0")
    is_open = Column(Boolean, nullable=False, default=False, server_default="0")
    is_followup = Column(Boolean, nullable=False, default=False, server_default="0")
    procedures_count = Column(Integer, nullable=False, default=0, server_default="0")


class FatoFinanceiro(Base):
    """1 linha por pagamento. Métricas: faturamento, inadimplência."""
    __tablename__ = "fato_financeiro"
    __table_args__ = (
        UniqueConstraint("tenant_id", "external_id", name="uk_fato_financeiro_external"),
        Index("ix_fato_financeiro_date", "tenant_id", "date_key"),
        Index("ix_fato_financeiro_year_month", "tenant_id", "year_month_key"),
        Index("ix_fato_financeiro_received", "tenant_id", "is_received"),
        Index("ix_fato_financeiro_payment_form", "tenant_id", "payment_form"),
    )
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    external_id = Column(String(64), nullable=False)
    date_key = Column(Date, nullable=True)
    year = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    year_month_key = Column(String(7), nullable=True)
    rebuilt_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    patient_external_id = Column(BigInteger, nullable=True)
    amount = Column(Numeric(12, 2), nullable=True)
    service_amount = Column(Numeric(12, 2), nullable=True)
    type = Column(String(50), nullable=True)
    payment_form = Column(String(50), nullable=True)
    is_received = Column(Boolean, nullable=False, default=False, server_default="0")
    is_confirmed = Column(Boolean, nullable=False, default=False, server_default="0")
    is_canceled = Column(Boolean, nullable=False, default=False, server_default="0")
