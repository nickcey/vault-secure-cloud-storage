#!/usr/bin/env python3
"""
Module de Chiffrement des Métadonnées
======================================

Auteur: Kiro AI
Date: 8 juillet 2026
Objectif: Protection complète des métadonnées (zero-knowledge)

Ce module chiffre/déchiffre les métadonnées des fichiers (nom, taille, type MIME, date)
avec AES-256-GCM pour que le serveur ne puisse jamais lire ces informations en clair.

Fonctionnalités:
- encrypt_metadata(): Chiffre un dictionnaire de métadonnées
- decrypt_metadata(): Déchiffre les métadonnées
- generate_metadata_key(): Génère une clé AES-256 aléatoire
"""

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
import json
import secrets
import base64


def generate_metadata_key():
    """
    Génère une clé AES-256 aléatoire pour chiffrer les métadonnées.
    
    Returns:
        bytes: Clé AES-256 (32 bytes)
    
    Example:
        >>> key = generate_metadata_key()
        >>> len(key)
        32
    """
    return secrets.token_bytes(32)


def encrypt_metadata(metadata_dict, aes_key):
    """
    Chiffre un dictionnaire de métadonnées avec AES-256-GCM.
    
    Le dictionnaire est sérialisé en JSON puis chiffré avec AES-256-GCM.
    GCM fournit à la fois la confidentialité (chiffrement) et l'authentification (tag).
    
    Args:
        metadata_dict (dict): Dictionnaire contenant les métadonnées à chiffrer
            Exemple: {
                "filename": "rapport.pdf",
                "mime_type": "application/pdf",
                "plaintext_size": 2457600,
                "original_uploaded_at": "2026-07-08T18:30:15.123456Z"
            }
        aes_key (bytes): Clé AES-256 (32 bytes)
    
    Returns:
        tuple: (encrypted_data, iv, tag)
            - encrypted_data (bytes): Données chiffrées
            - iv (bytes): Vecteur d'initialisation (12 bytes)
            - tag (bytes): Tag d'authentification GCM (16 bytes)
    
    Raises:
        ValueError: Si la clé n'est pas de 32 bytes
        TypeError: Si metadata_dict n'est pas un dictionnaire
    
    Example:
        >>> metadata = {"filename": "test.pdf", "size": 1024}
        >>> key = generate_metadata_key()
        >>> encrypted, iv, tag = encrypt_metadata(metadata, key)
        >>> len(iv)
        12
        >>> len(tag)
        16
    """
    # Validation
    if not isinstance(metadata_dict, dict):
        raise TypeError("metadata_dict doit être un dictionnaire")
    
    if len(aes_key) != 32:
        raise ValueError("aes_key doit faire 32 bytes (AES-256)")
    
    # Sérialisation JSON
    metadata_json = json.dumps(metadata_dict, ensure_ascii=False, sort_keys=True)
    metadata_bytes = metadata_json.encode('utf-8')
    
    # Génération IV (Initialization Vector) aléatoire
    # 12 bytes est la taille recommandée pour GCM
    iv = secrets.token_bytes(12)
    
    # Chiffrement AES-256-GCM
    aesgcm = AESGCM(aes_key)
    
    # GCM retourne ciphertext + tag (16 bytes) concaténés
    ciphertext_and_tag = aesgcm.encrypt(iv, metadata_bytes, None)
    
    # Séparation ciphertext et tag
    # Les 16 derniers bytes sont le tag d'authentification
    ciphertext = ciphertext_and_tag[:-16]
    tag = ciphertext_and_tag[-16:]
    
    return ciphertext, iv, tag


def decrypt_metadata(encrypted_data, iv, tag, aes_key):
    """
    Déchiffre les métadonnées chiffrées avec AES-256-GCM.
    
    Args:
        encrypted_data (bytes): Données chiffrées
        iv (bytes): Vecteur d'initialisation (12 bytes)
        tag (bytes): Tag d'authentification GCM (16 bytes)
        aes_key (bytes): Clé AES-256 (32 bytes)
    
    Returns:
        dict: Dictionnaire de métadonnées déchiffrées
    
    Raises:
        ValueError: Si la clé est invalide ou les données sont corrompues
        cryptography.exceptions.InvalidTag: Si le tag ne correspond pas (données altérées)
    
    Example:
        >>> metadata = {"filename": "test.pdf", "size": 1024}
        >>> key = generate_metadata_key()
        >>> encrypted, iv, tag = encrypt_metadata(metadata, key)
        >>> decrypted = decrypt_metadata(encrypted, iv, tag, key)
        >>> decrypted == metadata
        True
    """
    # Validation
    if len(aes_key) != 32:
        raise ValueError("aes_key doit faire 32 bytes (AES-256)")
    
    if len(iv) != 12:
        raise ValueError("iv doit faire 12 bytes")
    
    if len(tag) != 16:
        raise ValueError("tag doit faire 16 bytes")
    
    # Reconstruction du ciphertext + tag
    ciphertext_and_tag = encrypted_data + tag
    
    # Déchiffrement AES-256-GCM
    aesgcm = AESGCM(aes_key)
    
    try:
        plaintext_bytes = aesgcm.decrypt(iv, ciphertext_and_tag, None)
    except Exception as e:
        raise ValueError(f"Déchiffrement échoué : {str(e)}. "
                        "Clé invalide ou données corrompues.")
    
    # Désérialisation JSON
    metadata_json = plaintext_bytes.decode('utf-8')
    metadata_dict = json.loads(metadata_json)
    
    return metadata_dict


def encrypt_metadata_to_base64(metadata_dict, aes_key):
    """
    Chiffre les métadonnées et encode en base64 pour stockage en DB.
    
    Utilitaire qui combine encrypt_metadata() avec encodage base64.
    Utile pour stocker directement en base de données TEXT.
    
    Args:
        metadata_dict (dict): Métadonnées à chiffrer
        aes_key (bytes): Clé AES-256
    
    Returns:
        tuple: (encrypted_b64, iv_hex, tag_hex)
            - encrypted_b64 (str): Données chiffrées en base64
            - iv_hex (str): IV en hexadécimal
            - tag_hex (str): Tag en hexadécimal
    
    Example:
        >>> metadata = {"filename": "test.pdf"}
        >>> key = generate_metadata_key()
        >>> enc_b64, iv_hex, tag_hex = encrypt_metadata_to_base64(metadata, key)
        >>> isinstance(enc_b64, str)
        True
        >>> len(iv_hex)
        24  # 12 bytes = 24 caractères hex
    """
    encrypted, iv, tag = encrypt_metadata(metadata_dict, aes_key)
    
    encrypted_b64 = base64.b64encode(encrypted).decode('ascii')
    iv_hex = iv.hex()
    tag_hex = tag.hex()
    
    return encrypted_b64, iv_hex, tag_hex


def decrypt_metadata_from_base64(encrypted_b64, iv_hex, tag_hex, aes_key):
    """
    Déchiffre les métadonnées depuis base64/hex (stockage DB).
    
    Utilitaire qui combine décodage base64/hex avec decrypt_metadata().
    
    Args:
        encrypted_b64 (str): Données chiffrées en base64
        iv_hex (str): IV en hexadécimal
        tag_hex (str): Tag en hexadécimal
        aes_key (bytes): Clé AES-256
    
    Returns:
        dict: Métadonnées déchiffrées
    
    Example:
        >>> metadata = {"filename": "test.pdf"}
        >>> key = generate_metadata_key()
        >>> enc_b64, iv_hex, tag_hex = encrypt_metadata_to_base64(metadata, key)
        >>> decrypted = decrypt_metadata_from_base64(enc_b64, iv_hex, tag_hex, key)
        >>> decrypted == metadata
        True
    """
    encrypted = base64.b64decode(encrypted_b64)
    iv = bytes.fromhex(iv_hex)
    tag = bytes.fromhex(tag_hex)
    
    return decrypt_metadata(encrypted, iv, tag, aes_key)


# ══════════════════════════════════════════════════════════════
# TESTS UNITAIRES (Exécuter avec: python -m pytest metadata_crypto.py)
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("🔐 Tests Module metadata_crypto.py")
    print("=" * 60)
    
    # Test 1: Génération clé
    print("\n[Test 1] Génération clé AES-256...")
    key = generate_metadata_key()
    assert len(key) == 32, "Clé doit faire 32 bytes"
    print(f"✅ Clé générée : {key.hex()[:20]}... ({len(key)} bytes)")
    
    # Test 2: Chiffrement/Déchiffrement simple
    print("\n[Test 2] Chiffrement/Déchiffrement métadonnées...")
    metadata = {
        "filename": "rapport_confidentiel.pdf",
        "mime_type": "application/pdf",
        "plaintext_size": 2457600,
        "original_uploaded_at": "2026-07-08T18:30:15.123456Z"
    }
    
    encrypted, iv, tag = encrypt_metadata(metadata, key)
    print(f"✅ Chiffré : {len(encrypted)} bytes")
    print(f"   IV : {iv.hex()}")
    print(f"   Tag: {tag.hex()}")
    
    decrypted = decrypt_metadata(encrypted, iv, tag, key)
    assert decrypted == metadata, "Métadonnées déchiffrées différentes"
    print(f"✅ Déchiffré : {decrypted['filename']}")
    
    # Test 3: Base64 encoding
    print("\n[Test 3] Chiffrement avec base64 (stockage DB)...")
    enc_b64, iv_hex, tag_hex = encrypt_metadata_to_base64(metadata, key)
    print(f"✅ Encrypted (base64): {enc_b64[:50]}...")
    print(f"   IV (hex): {iv_hex}")
    print(f"   Tag (hex): {tag_hex}")
    
    decrypted2 = decrypt_metadata_from_base64(enc_b64, iv_hex, tag_hex, key)
    assert decrypted2 == metadata, "Déchiffrement base64 échoué"
    print(f"✅ Déchiffré depuis base64 : OK")
    
    # Test 4: Mauvaise clé (doit échouer)
    print("\n[Test 4] Tentative déchiffrement avec mauvaise clé...")
    wrong_key = generate_metadata_key()
    try:
        decrypt_metadata(encrypted, iv, tag, wrong_key)
        print("❌ ERREUR : Le déchiffrement aurait dû échouer")
    except ValueError as e:
        print(f"✅ Déchiffrement échoué comme prévu : {str(e)[:50]}...")
    
    # Test 5: Données altérées (tag invalide)
    print("\n[Test 5] Tentative déchiffrement avec données altérées...")
    corrupted_data = bytearray(encrypted)
    corrupted_data[0] ^= 0xFF  # Altérer le premier byte
    try:
        decrypt_metadata(bytes(corrupted_data), iv, tag, key)
        print("❌ ERREUR : Le déchiffrement aurait dû échouer")
    except ValueError as e:
        print(f"✅ Déchiffrement échoué comme prévu (données altérées)")
    
    # Test 6: Métadonnées avec caractères spéciaux
    print("\n[Test 6] Métadonnées avec caractères Unicode...")
    metadata_unicode = {
        "filename": "Rapport_été_2026_€_₽_¥.pdf",
        "description": "Contrat client Müller & Søn 🔐",
        "tags": ["financier", "été", "européen"]
    }
    enc, iv, tag = encrypt_metadata(metadata_unicode, key)
    dec = decrypt_metadata(enc, iv, tag, key)
    assert dec == metadata_unicode, "Unicode non préservé"
    print(f"✅ Unicode préservé : {dec['filename']}")
    
    print("\n" + "=" * 60)
    print("✅ TOUS LES TESTS RÉUSSIS !")
    print("=" * 60)
    print("\n📊 Statistiques:")
    print(f"   - Taille métadonnées original : {len(json.dumps(metadata))} bytes")
    print(f"   - Taille métadonnées chiffré : {len(encrypted)} bytes")
    print(f"   - Overhead : +{len(encrypted) - len(json.dumps(metadata))} bytes")
    print(f"   - IV : 12 bytes")
    print(f"   - Tag : 16 bytes")
    print(f"   - Total stockage : {len(encrypted) + 12 + 16} bytes")
