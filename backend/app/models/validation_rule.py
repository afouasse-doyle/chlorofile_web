from sqlalchemy import String, Text, Boolean, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class ValidationRule(Base, TimestampMixin):
    __tablename__ = "validation_rules"
    __table_args__ = {"schema": "appweb"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    rule_name: Mapped[str | None] = mapped_column(Text)                    # lien avec field_definitions.validation_rule
    year_suffix: Mapped[str] = mapped_column(String(9), nullable=False)   # '*' = toutes
    region: Mapped[str] = mapped_column(Text, nullable=False, default="*") # 'CN', 'ABIT'… ou '*'
    module: Mapped[str] = mapped_column(String(30), nullable=False)        # 'prescription' | 'parcelle'
    traitement: Mapped[str] = mapped_column(String(30), nullable=False)    # 'REB', '*' = tous
    traitement_match: Mapped[str] = mapped_column(Text, nullable=False, default="exact")  # 'exact' | 'in' | 'contains'
    champ: Mapped[str] = mapped_column(Text, nullable=False)
    rule_type: Mapped[str] = mapped_column(String(20), nullable=False)     # 'required', 'min', ...
    rule_value: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
