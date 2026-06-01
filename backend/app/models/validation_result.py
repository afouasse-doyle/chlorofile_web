import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, BigInteger, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ValidationResult(Base):
    __tablename__ = "validation_results"
    __table_args__ = {"schema": "appweb"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_ref1: Mapped[str] = mapped_column(String(64), nullable=False)
    run_uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rule_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("appweb.validation_rules.id"), nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
