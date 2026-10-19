"""
Module de gestion des clés RSA - Secure Cloud Storage
Gère la génération et le chiffrement/déchiffrement des clés RSA
"""

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization


def generate_rsa_keypair():
    """
    Génère une paire de clés RSA-2048
    
    Returns:
        tuple: (private_key, public_key)
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()
    return private_key, public_key


def serialize_private_key(private_key, password: bytes) -> bytes:
    """
    Chiffre la clé privée RSA avec un mot de passe (clé maîtresse)
    
    Args:
        private_key: la clé privée RSA
        password: clé maîtresse dérivée du mot de passe utilisateur
    
    Returns:
        bytes: clé privée chiffrée au format PEM
    """
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(password),
    )


def serialize_public_key(public_key) -> bytes:
    """
    Sérialise la clé publique RSA au format PEM
    
    Args:
        public_key: la clé publique RSA
    
    Returns:
        bytes: clé publique au format PEM
    """
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def deserialize_private_key(encrypted_private_key: bytes, password: bytes):
    """
    Déchiffre et charge une clé privée RSA
    
    Args:
        encrypted_private_key: clé privée chiffrée (PEM)
        password: clé maîtresse pour déchiffrer
    
    Returns:
        private_key: la clé privée RSA
    """
    return serialization.load_pem_private_key(
        encrypted_private_key,
        password=password,
    )


def deserialize_public_key(public_key_bytes: bytes):
    """
    Charge une clé publique RSA
    
    Args:
        public_key_bytes: clé publique au format PEM
    
    Returns:
        public_key: la clé publique RSA
    """
    return serialization.load_pem_public_key(public_key_bytes)


def rsa_encrypt(data: bytes, public_key) -> bytes:
    """
    Chiffre des données avec une clé publique RSA
    
    Args:
        data: données à chiffrer
        public_key: clé publique RSA
    
    Returns:
        bytes: données chiffrées
    """
    return public_key.encrypt(
        data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )


def rsa_decrypt(encrypted_data: bytes, private_key) -> bytes:
    """
    Déchiffre des données avec une clé privée RSA
    
    Args:
        encrypted_data: données chiffrées
        private_key: clé privée RSA
    
    Returns:
        bytes: données déchiffrées
    """
    return private_key.decrypt(
        encrypted_data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None,
        ),
    )