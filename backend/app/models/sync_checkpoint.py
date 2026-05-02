"""
Checkpoint de progresso de sync por (tenant, source, entity).
Permite saber até onde já foi importado e resumir grandes cargas históricas.
"""
from sqlalchemy import BigInteger, Column, Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.mysql import CHAR
from app.db.base import Base


class SyncCheckpoint(Base):
    __tablename__ = "sync_checkpoints"

    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), primary_key=True)
    source = Column(String(50), primary_key=True)
    entity = Column(String(50), primary_key=True)

    last_period_from = Column(Date, nullable=True)
    last_period_to = Column(Date, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    last_sync_job_id = Column(BigInteger, ForeignKey("sync_jobs.id"), nullable=True)
    status = Column(String(20), nullable=False, default="idle")
    total_records = Column(BigInteger, nullable=False, default=0)
