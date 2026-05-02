"""
Registro de execuções de sync com a Clinicorp.
Permite rastrear status, erros e duração de cada sync.
"""
from datetime import datetime
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.mysql import CHAR
from app.db.base import Base


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    source = Column(String(50), nullable=False)          # ex: "clinicorp"
    status = Column(String(20), nullable=False)          # pending | running | success | error
    ref_date_from = Column(String(10), nullable=False)
    ref_date_to = Column(String(10), nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    records_fetched = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
