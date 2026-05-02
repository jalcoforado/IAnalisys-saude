import uuid
from sqlalchemy import String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin, SoftDeleteMixin


class Tenant(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Configurações da clínica (doc 03)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="America/Sao_Paulo", nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="BRL", nullable=False)

    # Limites de IA por tenant (doc 03)
    ai_monthly_token_limit: Mapped[int] = mapped_column(default=100_000, nullable=False)

    # Relacionamentos
    user_tenants: Mapped[list["UserTenant"]] = relationship(back_populates="tenant")
