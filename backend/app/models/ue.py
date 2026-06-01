import uuid
from datetime import date
from sqlalchemy import String, Text, Numeric, Boolean, BigInteger, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Ue(Base, TimestampMixin):
    __tablename__ = "ue"
    __table_args__ = {"schema": "appweb"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ue_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False
    )
    user_ref1: Mapped[str] = mapped_column(String(64), nullable=False)
    year_suffix: Mapped[str] = mapped_column(String(9), nullable=False)
    unite_d_echantillonnage_ue: Mapped[str] = mapped_column(Text, nullable=False)

    # Champs prescription (issus du DBF)
    no_prescription: Mapped[str | None] = mapped_column(Text)
    secteur_intervention: Mapped[str | None] = mapped_column(Text)
    chantier: Mapped[str | None] = mapped_column(Text)
    uaf: Mapped[str | None] = mapped_column(Text)
    code_ratf: Mapped[str | None] = mapped_column(Text)
    contrat: Mapped[str | None] = mapped_column(Text)
    projet: Mapped[str | None] = mapped_column(Text)
    ha_prescription: Mapped[float | None] = mapped_column(Numeric(12, 4))
    entrepreneur_travaux: Mapped[str | None] = mapped_column(Text)
    debut: Mapped[date | None] = mapped_column(Date)
    fin: Mapped[date | None] = mapped_column(Date)
    traitement: Mapped[str | None] = mapped_column(Text)
    region: Mapped[str | None] = mapped_column(Text)

    # Champs à saisie manuelle
    gradient_intensite: Mapped[str | None] = mapped_column(Text)
    rayon: Mapped[float | None] = mapped_column(Numeric(10, 2))
    stocking_av_tr: Mapped[float | None] = mapped_column(Numeric(12, 4))

    statut_validation: Mapped[str] = mapped_column(String(20), nullable=False, default="non_valide")
    source_batch_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("appweb.import_batches.id")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    parcelles: Mapped[list["Parcelle"]] = relationship(back_populates="ue")  # noqa: F821
