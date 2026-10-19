"""
Hachage Argon2id de la VALEUR D'AUTHENTIFICATION (auth_value).

Architecture zero-knowledge :
- Le navigateur dérive PBKDF2-SHA256 (600 000 itérations, 512 bits) du mot de passe.
- Les 256 premiers bits = clé de compte (accountKey), ne quittent JAMAIS le navigateur.
- Les 256 suivants = valeur d'authentification (authValue), seule donnée secrète envoyée.
- Le serveur hache l'authValue avec Argon2id (salt aléatoire par compte) et ne connaît
  ni le mot de passe, ni la clé de compte.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

# Paramètres Argon2id recommandés (OWASP 2024)
_argon2_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,   # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_auth_value(auth_value: str) -> str:
    """Hache la valeur d'authentification avec Argon2id (format PHC)."""
    if not auth_value:
        raise ValueError("auth_value vide")
    return _argon2_hasher.hash(auth_value)


def verify_auth_value(auth_value: str, stored_hash: str) -> bool:
    """Vérifie la valeur d'authentification contre le hash Argon2id stocké."""
    if not auth_value or not stored_hash:
        return False
    try:
        return _argon2_hasher.verify(stored_hash, auth_value)
    except VerifyMismatchError:
        return False
    except (InvalidHashError, Exception):
        return False
