import uuid
from sqlalchemy import String, Text, ForeignKey, DateTime, func, Index, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class Permission(Base, TimestampMixin):
    """Catálogo de permissions granulares (ex: 'financeiro.write')."""

    __tablename__ = "permissions"
    __table_args__ = (Index("ix_permissions_module", "module"),)

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    module: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class RolePermission(Base):
    """Matriz role x permission por tenant. Cada tenant tem sua própria matriz."""

    __tablename__ = "role_permissions"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "role_id", "permission_id", name="pk_role_permissions"),
        Index("ix_role_permissions_role", "tenant_id", "role_id"),
    )

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    permission_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[str] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
