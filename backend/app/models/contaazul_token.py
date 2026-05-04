"""
Tokens OAuth da integração Conta Azul por tenant.
Cada tenant tem no máximo 1 token ativo.

Os campos `empresa_*` são populados via GET /v1/pessoas/conta-conectada
no momento do callback OAuth — servem pra exibir na UI qual empresa CA
está conectada (razão social + CNPJ) e dão certeza que o token amarra
no tenant correto.
"""
from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.mysql import CHAR
from app.db.base import Base


class ContaAzulToken(Base):
    __tablename__ = "contaazul_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(CHAR(36), ForeignKey("tenants.id"), nullable=False, unique=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    # Identificação da empresa CA conectada (de /v1/pessoas/conta-conectada).
    # Nullable: tokens antigos não têm; populado no callback OAuth.
    empresa_documento = Column(String(32), nullable=True)
    empresa_razao_social = Column(String(255), nullable=True)
    empresa_nome_fantasia = Column(String(255), nullable=True)
    empresa_data_fundacao = Column(Date, nullable=True)
    empresa_email = Column(String(255), nullable=True)

    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
