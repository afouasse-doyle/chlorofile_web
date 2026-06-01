"""
Sécurité : hachage des mots de passe (bcrypt) et jetons JWT.

Aucun mot de passe n'est jamais stocké ni loggé en clair.
La clé de signature JWT vient de WEB_SECRET_KEY (.env, hors dépôt).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from app.config import get_settings

settings = get_settings()

# bcrypt — algorithme de hachage de référence pour les mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Retourne le hash bcrypt d'un mot de passe en clair."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Vérifie un mot de passe en clair contre son hash stocké."""
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(
    subject: str | int,
    extra_claims: dict[str, Any] | None = None,
    expires_minutes: int | None = None,
) -> str:
    """
    Crée un JWT signé. `subject` (claim `sub`) = id de l'utilisateur.
    extra_claims permet d'embarquer user_ref1 et role pour éviter un aller-retour BD.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.session_absolute_minutes
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.web_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """Décode et valide un JWT. Lève jwt.PyJWTError si invalide/expiré."""
    return jwt.decode(token, settings.web_secret_key, algorithms=[settings.jwt_algorithm])
