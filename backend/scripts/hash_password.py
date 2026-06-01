"""
Génère un hash bcrypt à coller dans appweb.users.password_hash.

Sert quand tu ajoutes un utilisateur manuellement (INSERT SQL) avec un mot de
passe choisi dans la DB ou 1Password : tu hashes ici, et tu colles le hash
dans la colonne password_hash. La base ne stocke jamais le mot de passe en clair.

Usage (depuis backend/, venv activé) :
    python -m scripts.hash_password
    # mot de passe demandé en interactif, le hash s'affiche

Exemple d'INSERT à compléter avec le hash retourné
(l'email DOIT être en minuscules — le login normalise en minuscules) :
    INSERT INTO appweb.users (email, password_hash, full_name, user_ref1, role)
    VALUES ('user@coop.coop', '<HASH_ICI>', 'Nom Prénom', 'RBT', 'coop_user');
"""

import getpass
import sys

from app.core.security import hash_password


def main() -> int:
    password = getpass.getpass("Mot de passe à hacher : ")
    if len(password) < 8:
        print("Mot de passe trop court (minimum 8 caractères).", file=sys.stderr)
        return 1
    confirm = getpass.getpass("Confirmer : ")
    if password != confirm:
        print("Les mots de passe ne correspondent pas.", file=sys.stderr)
        return 1

    print("\nHash bcrypt (à coller dans password_hash) :\n")
    print(hash_password(password))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
