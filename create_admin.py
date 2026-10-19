"""
create_admin.py — Crée un compte administrateur compatible avec le mode zero-knowledge.

Le mot de passe n'est pas stocké : on calcule ici, comme le ferait le navigateur,
PBKDF2-SHA256 (600 000 itérations, 512 bits). La seconde moitié (valeur
d'authentification) est hachée avec Argon2id ; c'est tout ce que garde la base.
Un administrateur ne stocke pas de fichiers : il n'a donc pas de paire de clés.

Usage : python create_admin.py
"""
import getpass
import secrets
import sys

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def main():
    from app import app, PBKDF2_ITERATIONS
    from database.models import db, User
    from modules.argon2_auth import hash_auth_value

    print("\n=== Création d'un compte administrateur ===\n")
    username = input("Nom d'utilisateur : ").strip()
    email = input("Email : ").strip().lower()
    password = getpass.getpass("Mot de passe (12 caractères minimum) : ")
    if not username or not email or len(password) < 12:
        print("Champs invalides (mot de passe : 12 caractères minimum).")
        return 1

    with app.app_context():
        if User.query.filter((User.username == username) | (User.email == email)).first():
            print("Un utilisateur avec ce nom ou cet email existe déjà.")
            return 1
        salt = secrets.token_bytes(16)
        raw = PBKDF2HMAC(algorithm=hashes.SHA256(), length=64, salt=salt,
                         iterations=PBKDF2_ITERATIONS).derive(password.encode())
        admin = User(username=username, email=email,
                     auth_hash=hash_auth_value(raw[32:].hex()),
                     salt=salt.hex(), public_key='', encrypted_private_key='{}',
                     is_admin=True, plan='premium', language='fr')
        db.session.add(admin)
        db.session.commit()
        print(f"\nAdministrateur créé : {email}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
