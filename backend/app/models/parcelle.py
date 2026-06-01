import uuid
from datetime import date
from sqlalchemy import String, Text, Numeric, Boolean, BigInteger, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Parcelle(Base, TimestampMixin):
    __tablename__ = "parcelles"
    __table_args__ = {"schema": "appweb"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    parcelle_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False
    )
    ue_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("appweb.ue.id"), nullable=False)
    user_ref1: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_de_parcelle: Mapped[str] = mapped_column(Text, nullable=False)

    # Champs placette (issus du DBF)
    type_placette: Mapped[str | None] = mapped_column(Text)
    methode_production: Mapped[str | None] = mapped_column(Text)
    production_source: Mapped[str | None] = mapped_column(Text)
    date_production_source: Mapped[date | None] = mapped_column(Date)
    plant_ha: Mapped[float | None] = mapped_column(Numeric(12, 4))
    garmin: Mapped[str | None] = mapped_column(Text)
    secteur_intervention: Mapped[str | None] = mapped_column(Text)

    source_batch_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("appweb.import_batches.id")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    ue: Mapped["Ue"] = relationship(back_populates="parcelles")  # noqa: F821
