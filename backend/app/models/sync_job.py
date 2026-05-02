"""
Registro de execuções de sync com fontes externas (Clinicorp, Conta Azul).
Cada job representa a sincronização de UMA entidade num intervalo (ou estático).
"""
from sqlalchemy import BigInteger, Column, Date, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.mysql import CHAR
from app.db.base import Base


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False)
    source = Column(String(50), nullable=False)      # 'clinicorp', 'contaazul'
    entity = Column(String(50), nullable=False)      # 'business', 'appointments', ...
    status = Column(String(20), nullable=False)      # pending|running|success|error

    # Período (NULL para syncs estáticos sem data)
    period_from = Column(Date, nullable=True)
    period_to = Column(Date, nullable=True)

    # Tempos
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)

    # Métricas
    records_fetched = Column(BigInteger, nullable=True)
    records_inserted = Column(BigInteger, nullable=True)
    records_updated = Column(BigInteger, nullable=True)
    errors_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    __table_args__ = (
        Index("ix_sync_jobs_tenant_entity", "tenant_id", "entity", "created_at"),
        Index("ix_sync_jobs_tenant_status", "tenant_id", "status"),
    )
