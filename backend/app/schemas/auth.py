from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

ROLES = ("coop_user", "coop_admin", "fqcf_admin")


def _check_password_length(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Le mot de passe doit faire au moins 8 caractères")
    return value


def _check_role(value: str) -> str:
    if value not in ROLES:
        raise ValueError(f"role invalide (attendu : {', '.join(ROLES)})")
    return value


class TokenResponse(BaseModel):
    """Réponse de POST /auth/login."""
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    """Représentation publique d'un utilisateur — jamais le password_hash."""
    model_config = ConfigDict(from_attributes=True)

    user_uuid: uuid.UUID
    email: EmailStr
    full_name: str | None
    user_ref1: str | None
    role: str
    is_active: bool
    last_login_at: datetime | None


class UserCreate(BaseModel):
    """Création d'un utilisateur — réservé à l'administrateur FQCF."""
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str
    full_name: str | None = None
    user_ref1: str | None = None
    role: str = "coop_user"

    _v_pwd = field_validator("password")(_check_password_length)
    _v_role = field_validator("role")(_check_role)


class UserUpdate(BaseModel):
    """
    Édition d'un utilisateur — réservé à l'administrateur FQCF.
    Tous les champs sont optionnels (sémantique PATCH). Seuls les champs fournis
    sont modifiés. `password` fourni → réinitialisation du mot de passe.
    """
    model_config = ConfigDict(extra="forbid")

    full_name: str | None = None
    user_ref1: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None

    @field_validator("password")
    @classmethod
    def _v_pwd(cls, v: str | None) -> str | None:
        return None if v is None else _check_password_length(v)

    @field_validator("role")
    @classmethod
    def _v_role(cls, v: str | None) -> str | None:
        return None if v is None else _check_role(v)
