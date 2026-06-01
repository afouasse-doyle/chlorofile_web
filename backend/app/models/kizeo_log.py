from datetime import datetime
from sqlalchemy import String, Text, BigInteger, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KizeoGenerationLog(Base):
    __tablename__ = "kizeo_generation_log"
    __table_args__ = {"schema": "appweb"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_ref1: Mapped[str] = mapped_column(String(64), nullable=False)
    ue_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("appweb.ue.id"), nullable=False)
    year_suffix: Mapped[str] = mapped_column(String(9), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="simule")
    payload_json: Mapped[dict | None] = mapped_column(JSONB)
    response_json: Mapped[dict | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    generated_by: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
