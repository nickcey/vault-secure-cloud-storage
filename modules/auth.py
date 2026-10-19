"""
Module d'authentification - Secure Cloud Storage
Gère l'inscription, la connexion, la phrase mnémonique et l'authentification à double facteur
"""

import bcrypt
import secrets
import time
from mnemonic import Mnemonic
from database.models import db, User
from modules.crypto_manager import derive_key, generate_salt
from modules.key_manager import (
    generate_rsa_keypair,
    serialize_private_key,
    serialize_public_key,
    deserialize_private_key,
)


def hash_password(password: str) -> str:
    """Hache un mot de passe avec bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, password_hash: str) -> bool:
    """Vérifie un mot de passe contre son hash bcrypt"""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def generate_mnemonic_phrase() -> str:
    """Génère une phrase mnémonique de 12 mots (BIP39) en anglais"""
    mnemo = Mnemonic("english")
    return mnemo.generate(strength=128)


def derive_recovery_key(mnemonic_phrase: str, salt: bytes) -> bytes:
    """
    Dérive une clé de récupération à partir de la phrase mnémonique + sel utilisateur.
    Utilise PBKDF2 via derive_key pour que le sel soit bien appliqué.
    """
    mnemo = Mnemonic("english")
    seed = mnemo.to_seed(mnemonic_phrase, passphrase="")
    # Appliquer PBKDF2 avec le sel utilisateur pour lier la clé à l'utilisateur
    return derive_key(seed, salt)


def create_user(email: str, password: str):
    """Crée un nouvel utilisateur avec phrase mnémonique"""
    if User.query.filter_by(email=email).first():
        return None, None
    
    salt = generate_salt()
    master_key = derive_key(password, salt)
    
    private_key, public_key = generate_rsa_keypair()
    
    encrypted_private_key = serialize_private_key(private_key, master_key)
    public_key_bytes = serialize_public_key(public_key)
    
    mnemonic_phrase = generate_mnemonic_phrase()
    recovery_key = derive_recovery_key(mnemonic_phrase, salt)
    recovery_private_key = serialize_private_key(private_key, recovery_key)

    # SÉCURITÉ : aucun indice n'est stocké en clair côté serveur.
    # Un indice qui révèle une partie des mots de la phrase mnémonique dans la base
    # de données réduit l'entropie réelle de la récupération pour quiconque a accès
    # à la base (exactement le scénario contre lequel l'architecture zero-knowledge
    # est censée protéger). La récupération exige donc les 12 mots complets.
    recovery_hint = None

    otp_secret = ""  # Sera généré à la première connexion
    
    base_username = email.split('@')[0]
    username = base_username
    counter = 1
    while User.query.filter_by(username=username).first():
        username = f"{base_username}{counter}"
        counter += 1
    
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        encrypted_private_key=encrypted_private_key.decode(),
        public_key=public_key_bytes.decode(),
        salt=salt.hex(),
        otp_secret=otp_secret,
        recovery_private_key=recovery_private_key.decode(),
        recovery_hint=recovery_hint,
    )
    
    db.session.add(user)
    db.session.commit()
    
    return user, mnemonic_phrase


def login_user(email: str, password: str):
    """Vérifie email + mot de passe et retourne la clé privée RSA"""
    user = User.query.filter_by(email=email).first()
    
    if not user:
        return None, None
    
    if not check_password(password, user.password_hash):
        return None, None
    
    salt = bytes.fromhex(user.salt)
    master_key = derive_key(password, salt)
    
    try:
        private_key = deserialize_private_key(
            user.encrypted_private_key.encode(),
            master_key,
        )
    except Exception:
        return None, None
    
    return user, private_key


def verify_mnemonic(email: str, mnemonic_phrase: str):
    """Vérifie la phrase mnémonique et retourne un token de confirmation"""
    user = User.query.filter_by(email=email).first()
    
    if not user:
        return None, None
    
    if not user.recovery_private_key:
        return None, None
    
    salt = bytes.fromhex(user.salt)
    
    try:
        recovery_key = derive_recovery_key(mnemonic_phrase, salt)
        private_key = deserialize_private_key(
            user.recovery_private_key.encode(),
            recovery_key,
        )
    except Exception:
        return None, None
    
    token = secrets.token_urlsafe(32)
    user.recovery_token = token
    user.recovery_token_expiry = int(time.time()) + 900
    
    token_key = derive_key(token.encode(), salt)
    user.recovery_temp_key = serialize_private_key(private_key, token_key).decode()
    
    db.session.commit()
    
    return user, token


def confirm_recovery(email: str, token: str, new_password: str):
    """
    Confirme la récupération avec le token et change le mot de passe.
    Génère une nouvelle phrase mnémonique.
    Retourne (user, private_key, new_mnemonic).
    """
    user = User.query.filter_by(email=email).first()
    
    if not user:
        return None, None, None
    
    if not user.recovery_token or user.recovery_token != token:
        return None, None, None
    
    if int(time.time()) > user.recovery_token_expiry:
        return None, None, None
    
    if not user.recovery_temp_key:
        return None, None, None
    
    salt = bytes.fromhex(user.salt)
    
    try:
        token_key = derive_key(token.encode(), salt)
        private_key = deserialize_private_key(
            user.recovery_temp_key.encode(),
            token_key,
        )
    except Exception:
        return None, None, None
    
    new_salt = generate_salt()
    new_master_key = derive_key(new_password, new_salt)
    
    user.password_hash = hash_password(new_password)
    user.salt = new_salt.hex()
    user.encrypted_private_key = serialize_private_key(private_key, new_master_key).decode()
    
    new_mnemonic = generate_mnemonic_phrase()
    new_recovery_key = derive_recovery_key(new_mnemonic, new_salt)
    user.recovery_private_key = serialize_private_key(private_key, new_recovery_key).decode()

    # SÉCURITÉ : pas d'indice en clair (voir create_user ci-dessus pour la justification).
    user.recovery_hint = None

    user.recovery_token = None
    user.recovery_token_expiry = 0
    user.recovery_temp_key = None
    
    db.session.commit()
    
    return user, private_key, new_mnemonic


# NOTE D'ARCHITECTURE — AUTHENTIFICATION À DEUX FACTEURS (2FA)
# ==============================================================
# Le 2FA réellement actif dans Vault est un code à usage unique généré
# aléatoirement et envoyé par email à chaque connexion et à chaque
# téléchargement sensible (voir app.py : génération du code, envoi par
# Flask-Mail, puis vérification par comparaison à temps constant avec
# hmac.compare_digest sur le champ otp_secret, qui sert ici de code
# temporaire et non de secret TOTP).
#
# D'anciennes fonctions verify_otp()/generate_otp_uri(), fondées sur la
# bibliothèque pyotp pour un 2FA par application (Google Authenticator,
# TOTP RFC 6238), existaient dans ce module mais n'étaient appelées nulle
# part dans l'application : elles ont été retirées pour que le code ne
# documente que le mécanisme qui tourne réellement. Un 2FA par
# application pourra être ajouté comme évolution future si besoin
# (voir le mémoire, chapitre 5, perspectives).