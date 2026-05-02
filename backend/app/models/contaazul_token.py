"""
Tokens OAuth da integração Conta Azul por tenant.
Cada tenant tem no máximo 1 token ativo.
"""
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.mysql import CHAR
from app.db.base import Base


class ContaAzulToken(Base):
    __tablename__ = "contaazul_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False, unique=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
