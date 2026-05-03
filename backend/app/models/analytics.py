"""
Modelos da camada ANALYTICS — dimensões e fatos para dashboards e IA.

dim_*  → entidades pré-formatadas para JOINs (calendário, paciente, profissional)
fato_* → eventos quantitativos com FK lógica para dimensões
"""
from sqlalchemy import (
    BigInteger, Boolean, Column, Date, DateTime, ForeignKey, Index, Integer,
    String, UniqueConstraint, func
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
