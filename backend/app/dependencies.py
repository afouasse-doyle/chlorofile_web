"""
Dépendances FastAPI partagées : résolution de la session et de l'utilisateur courant.

Le JWT ne porte qu'un pointeur de session (sid). Tout le contrôle de durée de vie
est fait côté serveur via appweb.user_sessions :
  - inactivité  : now - last_seen_at > session_idle_minutes      → session fermée
  - absolu      : now >= expires_at                              → session fermée
  - révocation  : revoked_at IS NOT NULL                         → session refusée

C'est aussi ici que le user_ref1 entre dans le système — depuis l'utilisateur
résolu via la session, jamais depuis la requête (clé RLS).
"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import decode_token
from app.database import get_db
from app.models.user import User
from app.models.user_session import UserSession

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

_CRED_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Identifiants invalides",
    headers={"WWW-Authenticate": "Bearer"},
)
_SESSION_EXPIRED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Session expirée, veuillez vous reconnecter",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_session(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserSession:
    """
    Valide le JWT puis la session côté serveur (inactivité, absolu, révocation).
    Met à jour last_seen_at (throttlé) à chaque appel.
    """
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise _CRED_EXC

    sid = payload.get("sid")
    if not sid:
        raise _CRED_EXC

    session = (
        db.query(UserSession)
        .filter(UserSession.session_uuid == sid)
        .first()
    )
    if session is None or session.revoked_at is not None:
        raise _CRED_EXC

    now = datetime.now(timezone.utc)

    # Timeout absolu — borne dure fixée à la connexion
    if now >= session.expires_at:
        session.revoked_at = now
        db.commit()
        raise _SESSION_EXPIRED

    # Timeout d'inactivité — temps écoulé depuis la dernière activité
    idle_limit = timedelta(minutes=settings.session_idle_minutes)
    if now - session.last_seen_at > idle_limit:
        session.revoked_at = now
        db.commit()
        raise _SESSION_EXPIRED

    # Glissement de l'activité (throttlé pour éviter un UPDATE à chaque requête)
    if now - session.last_seen_at > timedelta(seconds=settings.session_touch_seconds):
        session.last_seen_at = now
        db.commit()

    return session


def get_current_user(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
) -> User:
    """Charge l'utilisateur de la session courante et vérifie qu'il est actif."""
    user = db.query(User).filter(User.id == session.user_id).first()
    if user is None or not user.is_active:
        raise _CRED_EXC
    return user


def get_active_user_ref1(current_user: User = Depends(get_current_user)) -> str:
    """
    Retourne le user_ref1 de l'utilisateur courant.
    Refuse les administrateurs globaux (user_ref1 NULL) sur les routes qui
    exigent une coop précise — sélection de coop à implémenter.
    """
    if not current_user.user_ref1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune coop associée à ce compte. Sélection de coop requise.",
        )
    return current_user.user_ref1


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Réserve une route aux administrateurs (coop_admin ou fqcf_admin)."""
    if current_user.role not in ("coop_admin", "fqcf_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs",
        )
    return current_user


def require_fqcf_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Réserve une route au seul administrateur global FQCF.
    Utilisé pour la gestion des comptes — ni les coop_user ni les coop_admin
    ne peuvent créer ou éditer des utilisateurs.
    """
    if current_user.role != "fqcf_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé à l'administrateur FQCF",
        )
    return current_user
