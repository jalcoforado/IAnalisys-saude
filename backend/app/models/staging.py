"""
Modelos de staging: armazenam dados brutos da API Clinicorp antes de transformação.
Cada tabela tem: tenant_id, raw_data (JSON), período referência, synced_at.
"""
from datetime import datetime
from sqlalchemy import (
    BigInteger, Column, DateTime, ForeignKey, Index, Integer,
    String, Text, func
)
from sqlalchemy.dialects.mysql import JSON, CHAR
from app.db.base import Base


class StgAppointment(Base):
    __tablename__ = "stg_appointments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    ref_date_from = Column(String(10), nullable=False)   # YYYY-MM-DD
    ref_date_to = Column(String(10), nullable=False)
    raw_data = Column(JSON, nullable=False)
    synced_at = Column(DateTime, nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_stg_appointments_tenant_ref", "tenant_id", "ref_date_from", "ref_date_to"),
    )


class StgEstimate(Base):
    __tablename__ = "stg_estimates"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    ref_date_from = Column(String(10), nullable=False)
    ref_date_to = Column(String(10), nullable=False)
    raw_data = Column(JSON, nullable=False)
    synced_at = Column(DateTime, nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_stg_estimates_tenant_ref", "tenant_id", "ref_date_from", "ref_date_to"),
    )


class StgCashFlow(Base):
    __tablename__ = "stg_cash_flow"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    ref_date_from = Column(String(10), nullable=False)
    ref_date_to = Column(String(10), nullable=False)
    raw_data = Column(JSON, nullable=False)
    synced_at = Column(DateTime, nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_stg_cash_flow_tenant_ref", "tenant_id", "ref_date_from", "ref_date_to"),
    )


class StgPayment(Base):
    __tablename__ = "stg_payments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    ref_date_from = Column(String(10), nullable=False)
    ref_date_to = Column(String(10), nullable=False)
    raw_data = Column(JSON, nullable=False)
    synced_at = Column(DateTime, nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_stg_payments_tenant_ref", "tenant_id", "ref_date_from", "ref_date_to"),
    )


class StgAnalytics(Base):
    __tablename__ = "stg_analytics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    ref_date_from = Column(String(10), nullable=False)
    ref_date_to = Column(String(10), nullable=False)
    raw_data = Column(JSON, nullable=False)
    synced_at = Column(DateTime, nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_stg_analytics_tenant_ref", "tenant_id", "ref_date_from", "ref_date_to"),
    )


class StgFinancialSummary(Base):
    __tablename__ = "stg_financial_summary"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    ref_date_from = Column(String(10), nullable=False)
    ref_date_to = Column(String(10), nullable=False)
    raw_data = Column(JSON, nullable=False)
    synced_at = Column(DateTime, nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_stg_financial_summary_tenant_ref", "tenant_id", "ref_date_from", "ref_date_to"),
    )


class StgEstimatesConversion(Base):
    __tablename__ = "stg_estimates_conversion"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    ref_date_from = Column(String(10), nullable=False)
    ref_date_to = Column(String(10), nullable=False)
    raw_data = Column(JSON, nullable=False)
    synced_at = Column(DateTime, nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_stg_estimates_conversion_tenant_ref", "tenant_id", "ref_date_from", "ref_date_to"),
    )
