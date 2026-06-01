"""
Sécurité : hachage des mots de passe (bcrypt) et jetons JWT.

Aucun mot de passe n'est jamais stocké ni loggé en clair.
La clé de signature JWT vient de WEB_SECRET_KEY (.env, hors dépôt).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.config import get_settings

settings = get_settings()

# bcrypt limite l'entrée à 72 octets — on tronque de façon cohérente au hachage
# et à la vérification (les octets au-delà de 72 sont ignorés par l'algorithme).
_BCRYPT_MAX_BYTES = 72


def _to_bcrypt_bytes(plain_password: str) -> bytes:
    return plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(plain_password: str) -> str:
    """Retourne le hash bcrypt d'un mot de passe en clair."""
    return bcrypt.hashpw(_to_bcrypt_bytes(plain_password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Vérifie un mot de passe en clair contre son hash stocké."""
    try:
        return bcrypt.checkpw(_to_bcrypt_bytes(plain_password), password_hash.encode("utf-8"))
    except ValueError:
        # password_hash mal formé (ex: pas un hash bcrypt)
        return False


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
