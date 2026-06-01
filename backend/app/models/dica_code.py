from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DicaCode(Base):
    """Référence des codes DICA : code_dica → traitement (dérivation)."""
    __tablename__ = "dica_codes"
    __table_args__ = {"schema": "appweb"}

    code_dica: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str | None] = mapped_column(Text)
    traitement: Mapped[str | None] = mapped_column(Text)
