"""
Router : authentification

POST   /auth/login         → email + mot de passe → JWT
POST   /auth/logout        → révoque la session courante
GET    /auth/me            → profil de l'utilisateur connecté

Gestion des comptes — réservée au seul administrateur FQCF (role=fqcf_admin) :
GET    /auth/users         → liste des utilisateurs
POST   /auth/users         → création d'un utilisateur
PATCH  /auth/users/{uuid}  → édition d'un utilisateur

Il n'y a PAS d'auto-inscription. Ni les coop_user ni les coop_admin ne peuvent
créer ou modifier un compte — seul fqcf_admin (toi) le peut. Le script CLI
backend/scripts/create_user.py reste disponible pour créer le tout premier admin
(avant qu'un fqcf_admin n'existe).
"""

import logging
import uuid as uuid_lib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.dependencies import get_current_session, get_current_user, require_fqcf_admin
from app.models.login_attempt import LoginAttempt
from app.models.user import User
from app.models.user_session import UserSession
from app.schemas.auth import TokenResponse, UserCreate, UserOut, UserUpdate

settings = get_settings()


def _count_recent_failures(db: Session, *, email: str, ip: str | None, since) -> tuple[int, int]:
    """Compte les échecs récents (depuis `since`) par email et par IP."""
    email_fails = (
        db.query(func.count(LoginAttempt.id))
        .filter(
            LoginAttempt.email == email,
            LoginAttempt.success.is_(False),
            LoginAttempt.created_at >= since,
        )
        .scalar()
    ) or 0
    ip_fails = 0
    if ip:
        ip_fails = (
            db.query(func.count(LoginAttempt.id))
            .filter(
                LoginAttempt.ip_address == ip,
                LoginAttempt.success.is_(False),
                LoginAttempt.created_at >= since,
            )
            .scalar()
        ) or 0
    return email_fails, ip_fails

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Connexion par email (champ `username` du formulaire OAuth2) + mot de passe.
    Ouvre une session serveur (appweb.user_sessions) et retourne un JWT qui
    pointe vers elle (claim `sid`).

    Anti-brute-force : verrouillage par fenêtre glissante (email + IP). Au-delà
    du seuil, refus immédiat (429) sans vérifier le mot de passe.
    """
    now = datetime.now(timezone.utc)
    email_norm = (form.username or "").strip().lower()
    ip = request.client.host if request.client else None
    window_start = now - timedelta(minutes=settings.login_lockout_minutes)

    # 1. Verrouillage : trop d'échecs récents par email ou par IP ?
    email_fails, ip_fails = _count_recent_failures(
        db, email=email_norm, ip=ip, since=window_start
    )
    if (
        email_fails >= settings.login_max_attempts_email
        or ip_fails >= settings.login_max_attempts_ip
    ):
        # On ne journalise PAS ce refus : la fenêtre reste basée sur les vrais
        # échecs et se résorbe d'elle-même après login_lockout_minutes.
        logger.warning(
            "Login verrouillé email=%s ip=%s email_fails=%d ip_fails=%d",
            email_norm, ip, email_fails, ip_fails,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives. Réessayez plus tard.",
            headers={"Retry-After": str(settings.login_lockout_minutes * 60)},
        )

    # 2. Vérification des identifiants
    user = db.query(User).filter(User.email == email_norm).first()
    ok = (
        user is not None
        and user.is_active
        and verify_password(form.password, user.password_hash)
    )

    # 3. Journalisation de la tentative (succès comme échec)
    db.add(LoginAttempt(email=email_norm, ip_address=ip, success=ok))

    if not ok:
        db.commit()  # persiste l'échec avant de répondre
        # Message volontairement générique — pas de fuite d'information
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )

    user.last_login_at = now

    # Ouverture de la session côté serveur (idle + absolu + révocation)
    session = UserSession(
        user_id=user.id,
        expires_at=now + timedelta(minutes=settings.session_absolute_minutes),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(session)
    db.flush()  # obtient session.session_uuid

    token = create_access_token(
        subject=user.id,
        extra_claims={
            "sid": str(session.session_uuid),
            "user_ref1": user.user_ref1,
            "role": user.role,
        },
        expires_minutes=settings.session_absolute_minutes,
    )
    db.commit()
    logger.info("Login ok user_id=%s user_ref1=%s role=%s sid=%s",
                user.id, user.user_ref1, user.role, session.session_uuid)
    return TokenResponse(access_token=token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    session: UserSession = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Révoque immédiatement la session courante (déconnexion réelle)."""
    session.revoked_at = datetime.now(timezone.utc)
    db.commit()
    logger.info("Logout sid=%s user_id=%s", session.session_uuid, session.user_id)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    """Profil de l'utilisateur connecté."""
    return current_user


# ---------------------------------------------------------------------------
# Gestion des comptes — réservée à fqcf_admin
# ---------------------------------------------------------------------------

@router.get("/users", response_model=list[UserOut])
def list_users(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_fqcf_admin),
):
    """Liste les utilisateurs. Par défaut, seulement les actifs."""
    q = db.query(User)
    if not include_inactive:
        q = q.filter(User.is_active.is_(True))
    return q.order_by(User.id).all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_fqcf_admin),
):
    """Crée un utilisateur. Réservé à fqcf_admin."""
    email_norm = str(payload.email).strip().lower()
    if db.query(User).filter(User.email == email_norm).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email déjà utilisé")

    user = User(
        email=email_norm,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        user_ref1=payload.user_ref1,
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Utilisateur créé par admin=%s email=%s user_ref1=%s role=%s",
                admin.id, user.email, user.user_ref1, user.role)
    return user


@router.patch("/users/{user_uuid}", response_model=UserOut)
def update_user(
    user_uuid: uuid_lib.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_fqcf_admin),
):
    """
    Édite un utilisateur (PATCH). Réservé à fqcf_admin.
    Un mot de passe fourni est réinitialisé (haché). Une désactivation révoque
    immédiatement les sessions actives de l'utilisateur.
    """
    user = db.query(User).filter(User.user_uuid == user_uuid).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    data = payload.model_dump(exclude_unset=True)  # uniquement les champs fournis

    # Garde-fou : l'admin ne peut pas se verrouiller lui-même
    if user.id == admin.id:
        if data.get("is_active") is False:
            raise HTTPException(status_code=400, detail="Impossible de désactiver votre propre compte")
        if "role" in data and data["role"] != "fqcf_admin":
            raise HTTPException(status_code=400, detail="Impossible de retirer votre propre rôle admin")

    if "password" in data:
        user.password_hash = hash_password(data.pop("password"))

    for field, value in data.items():
        setattr(user, field, value)

    # Désactivation → coupe les sessions en cours immédiatement
    if data.get("is_active") is False:
        db.query(UserSession).filter(
            UserSession.user_id == user.id,
            UserSession.revoked_at.is_(None),
        ).update({UserSession.revoked_at: datetime.now(timezone.utc)})

    db.commit()
    db.refresh(user)
    logger.info("Utilisateur édité par admin=%s cible=%s champs=%s",
                admin.id, user.id, list(data.keys()))
    return user
