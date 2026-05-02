import uuid
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.mixins import TimestampMixin


# Papéis definidos em docs/03_MULTI_TENANT_MODEL.md
ROLE_SAAS_ADMIN = "saas_admin"
ROLE_TENANT_ADMIN = "tenant_admin"
ROLE_MANAGER = "manager"
ROLE_FINANCIAL = "financial"
ROLE_COMMERCIAL = "commercial"
ROLE_OPERATIONS = "operations"

VALID_ROLES = (
    ROLE_SAAS_ADMIN,
    ROLE_TENANT_ADMIN,
    ROLE_MANAGER,
    ROLE_FINANCIAL,
    ROLE_COMMERCIAL,
    ROLE_OPERATIONS,
)


class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relacionamentos
    user_tenants: Mapped[list["UserTenant"]] = relationship(back_populates="role")
