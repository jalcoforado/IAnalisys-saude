import uuid
from sqlalchemy import String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin


class UserTenant(Base, TimestampMixin):
    """
    Associação entre usuário e tenant.
    Um usuário pode pertencer a múltiplos tenants com papéis diferentes.
    (docs/03_MULTI_TENANT_MODEL.md)
    """

    __tablename__ = "user_tenants"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relacionamentos
    user: Mapped["User"] = relationship(back_populates="user_tenants")
    tenant: Mapped["Tenant"] = relationship(back_populates="user_tenants")
    role: Mapped["Role"] = relationship(back_populates="user_tenants")
