"""
Création d'un utilisateur du portail en ligne de commande.

Sert à créer le premier administrateur (avant qu'une UI d'admin existe),
ou à dépanner. Le mot de passe est haché (bcrypt) avant insertion.

Usage (depuis backend/, venv activé) :
    python -m scripts.create_user --email a.fouasse-doyle@fqcf.coop --role fqcf_admin
    python -m scripts.create_user --email user@coop.coop --user-ref1 RBT --role coop_user

Le mot de passe est demandé de façon interactive (jamais en argument CLI).
"""

import argparse
import getpass
import sys

from app.core.security import hash_password
from app.database import SessionLocal
from app.models.user import User

ROLES = ("coop_user", "coop_admin", "fqcf_admin")


def main() -> int:
    parser = argparse.ArgumentParser(description="Créer un utilisateur du portail")
    parser.add_argument("--email", required=True)
    parser.add_argument("--full-name", default=None)
    parser.add_argument("--user-ref1", default=None, help="Code coop (NULL pour admin global)")
    parser.add_argument("--role", default="coop_user", choices=ROLES)
    args = parser.parse_args()

    password = getpass.getpass("Mot de passe : ")
    confirm = getpass.getpass("Confirmer : ")
    if password != confirm:
        print("Les mots de passe ne correspondent pas.", file=sys.stderr)
        return 1
    if len(password) < 8:
        print("Mot de passe trop court (minimum 8 caractères).", file=sys.stderr)
        return 1

    email_norm = args.email.strip().lower()
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email_norm).first():
            print(f"Email déjà utilisé : {email_norm}", file=sys.stderr)
            return 1
        user = User(
            email=email_norm,
            password_hash=hash_password(password),
            full_name=args.full_name,
            user_ref1=args.user_ref1,
            role=args.role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"Utilisateur créé : id={user.id} email={user.email} "
              f"user_ref1={user.user_ref1} role={user.role}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
