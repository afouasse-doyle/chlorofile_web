from decimal import Decimal

from sqlalchemy import String, Text, Boolean, Integer, BigInteger, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class FieldDefinition(Base):
    """
    Catalogue des champs (pack-driven par year_suffix). Pilote l'UI et la validation.
    requirement : 'R' (requis), 'O' (optionnel), 'C' (conditionnel → validation_rule).
    Seed : docs/chlorofile_web/field_definitions_seed.sql.
    """

    __tablename__ = "field_definitions"
    __table_args__ = {"schema": "appweb"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity: Mapped[str] = mapped_column(Text, nullable=False)              # 'ue' | 'parcelle'
    year_suffix: Mapped[str] = mapped_column(Text, nullable=False, default="*")
    field_name: Mapped[str] = mapped_column(Text, nullable=False)          # = nom de colonne
    label: Mapped[str] = mapped_column(Text, nullable=False)
    data_type: Mapped[str] = mapped_column(Text, nullable=False)           # texte/entier/decimal/date/booleen/liste
    source: Mapped[str] = mapped_column(Text, nullable=False)              # auto/manuel/derive
    requirement: Mapped[str] = mapped_column(Text, nullable=False, default="O")  # R/O/C
    list_name: Mapped[str | None] = mapped_column(Text)                    # list_options.list_name ou 'dica_codes'
    validation_rule: Mapped[str | None] = mapped_column(Text)              # rule_name si requirement='C'
    min_value: Mapped[Decimal | None] = mapped_column(Numeric)
    max_value: Mapped[Decimal | None] = mapped_column(Numeric)
    is_editable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int | None] = mapped_column(Integer)
    help_text: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
