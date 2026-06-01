import uuid
from datetime import date
from sqlalchemy import String, Text, Numeric, Boolean, Integer, BigInteger, Date, ForeignKey
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

    # --- Champs auto (issus du DBF) ---
    code_dica: Mapped[str | None] = mapped_column(Text)            # TY_TRAIT → code_dica
    no_prescription: Mapped[str | None] = mapped_column(Text)
    secteur_intervention: Mapped[str | None] = mapped_column(Text)
    chantier: Mapped[str | None] = mapped_column(Text)
    uaf: Mapped[str | None] = mapped_column(Text)
    code_ratf: Mapped[str | None] = mapped_column(Text)
    contrat: Mapped[str | None] = mapped_column(Text)
    projet: Mapped[str | None] = mapped_column(Text)
    ha_prescription: Mapped[float | None] = mapped_column(Numeric(12, 4))  # somme des lignes
    entrepreneur_travaux: Mapped[str | None] = mapped_column(Text)
    debut: Mapped[date | None] = mapped_column(Date)
    fin: Mapped[date | None] = mapped_column(Date)

    # --- Champ dérivé ---
    traitement: Mapped[str | None] = mapped_column(Text)           # dérivé de code_dica

    # --- Champs manuels (saisie web) ---
    region: Mapped[str | None] = mapped_column(Text)
    gradient_intensite: Mapped[str | None] = mapped_column(Text)
    rayon: Mapped[float | None] = mapped_column(Numeric(10, 2))
    plant_ha: Mapped[float | None] = mapped_column(Numeric(12, 4))
    traitement_ps: Mapped[str | None] = mapped_column(Text)
    denombrement_cn: Mapped[int | None] = mapped_column(Integer)
    taux_occ_andain: Mapped[float | None] = mapped_column(Numeric(12, 4))
    nb_parcelle_ue: Mapped[int | None] = mapped_column(Integer)
    parcelle_faite: Mapped[str | None] = mapped_column(Text)
    directive_op: Mapped[str | None] = mapped_column(Text)
    ha_net: Mapped[float | None] = mapped_column(Numeric(12, 4))
    origine: Mapped[str | None] = mapped_column(Text)
    preparation_de_terrain: Mapped[str | None] = mapped_column(Text)
    type_de_degagement: Mapped[str | None] = mapped_column(Text)
    equip_utilise: Mapped[str | None] = mapped_column(Text)
    methode_andains: Mapped[str | None] = mapped_column(Text)
    nb_si_reboisement: Mapped[float | None] = mapped_column(Numeric(12, 4))
    plant_max: Mapped[float | None] = mapped_column(Numeric(12, 4))
    plant_reboise: Mapped[float | None] = mapped_column(Numeric(12, 4))
    ms_propice: Mapped[float | None] = mapped_column(Numeric(12, 4))
    note_1: Mapped[str | None] = mapped_column(Text)
    andain: Mapped[float | None] = mapped_column(Numeric(12, 4))
    entre_andain: Mapped[float | None] = mapped_column(Numeric(12, 4))
    stocking_av_tr: Mapped[float | None] = mapped_column(Numeric(12, 4))

    # --- Métadonnées ---
    statut_validation: Mapped[str] = mapped_column(String(20), nullable=False, default="non_valide")
    source_batch_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("appweb.import_batches.id")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    parcelles: Mapped[list["Parcelle"]] = relationship(back_populates="ue")  # noqa: F821
