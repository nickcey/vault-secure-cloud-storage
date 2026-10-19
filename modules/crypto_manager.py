"""
Module cryptographique - Secure Cloud Storage
Gère le chiffrement/déchiffrement AES-256-GCM et la dérivation de clé
"""

import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


def derive_key(password, salt: bytes) -> bytes:
    """
    Dérive une clé AES-256 à partir d'un mot de passe et d'un sel
    Utilise PBKDF2 avec 600 000 itérations
    Accepte aussi bien des bytes que des strings
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600000,
    )
    return kdf.derive(password if isinstance(password, bytes) else password.encode())


def generate_salt() -> bytes:
    """Génère un sel aléatoire de 16 octets"""
    return os.urandom(16)


def encrypt_file(file_data: bytes, key: bytes) -> tuple:
    """Chiffre des données avec AES-256-GCM"""
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, file_data, None)
    return nonce, ciphertext


def decrypt_file(nonce: bytes, ciphertext: bytes, key: bytes) -> bytes:
    """Déchiffre des données avec AES-256-GCM"""
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext


def generate_aes_key() -> bytes:
    """Génère une clé AES-256 aléatoire"""
    return AESGCM.generate_key(bit_length=256)