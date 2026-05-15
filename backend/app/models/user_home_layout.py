from typing import Any

from sqlalchemy import ForeignKey, Integer, JSON, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin


class UserHomeLayout(Base, TimestampMixin):
    """Layout customizado do "Meu IAnalisys" (My-Analisys) por usuário/tenant.

    `layout_json` é uma lista de itens compatíveis com react-grid-layout:
        [{"widget_id": str, "x": int, "y": int, "w": int, "h": int}, ...]

    Ausência de linha = usuário nunca customizou (front aplica default da role).
    """

    __tablename__ = "user_home_layouts"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "user_id", name="pk_user_home_layouts"),
    )

    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    layout_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
