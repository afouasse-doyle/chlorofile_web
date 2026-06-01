from sqlalchemy import String, Text, Integer, Boolean, BigInteger, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class DbfFieldAlias(Base, TimestampMixin):
    __tablename__ = "dbf_field_aliases"
    __table_args__ = (
        UniqueConstraint(
            "source_field", "target_field", "source_type",
            name="uq_dbf_field_aliases",
        ),
        {"schema": "appweb"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_field: Mapped[str] = mapped_column(Text, nullable=False)
    target_field: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="dbf")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
