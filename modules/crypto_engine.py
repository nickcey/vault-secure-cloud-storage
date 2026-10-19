"""
Module de chiffrement/déchiffrement des fichiers - Secure Cloud Storage
Supporte le chiffrement streaming pour les gros fichiers (AES-256-GCM)
"""

import os
import uuid
from modules.crypto_manager import generate_aes_key
from modules.key_manager import rsa_encrypt, rsa_decrypt, deserialize_public_key

# Taille des chunks pour le chiffrement streaming : 8 Mo
CHUNK_SIZE = 8 * 1024 * 1024


def encrypt_file_for_storage(file_data: bytes, public_key_pem: str) -> dict:
    """
    Chiffre un fichier (en mémoire) pour stockage côté serveur.
    Utilisé pour les petits fichiers uniquement.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aes_key = generate_aes_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(aes_key)
    ciphertext = aesgcm.encrypt(nonce, file_data, None)

    public_key = deserialize_public_key(public_key_pem.encode())
    encrypted_aes_key = rsa_encrypt(aes_key, public_key)
    tag = ciphertext[-16:]

    return {
        'encrypted_data': ciphertext,
        'encrypted_aes_key': encrypted_aes_key,
        'nonce': nonce,
        'tag': tag
    }


def encrypt_file_streaming(file_stream, output_path: str, public_key_pem: str) -> dict:
    """
    Chiffre un fichier en streaming (chunk par chunk) et écrit directement sur le disque.
    Utilisé pour les gros fichiers afin d'éviter de tout charger en RAM.

    Args:
        file_stream: objet fichier ou werkzeug FileStorage avec méthode read()
        output_path: chemin du fichier .enc de sortie
        public_key_pem: clé publique RSA de l'utilisateur

    Returns:
        dict: {encrypted_aes_key, nonce, tag, file_size}
    """
    from Crypto.Cipher import AES

    aes_key = generate_aes_key()
    nonce = os.urandom(16)  # 16 bytes pour AES-GCM avec pycryptodome

    public_key = deserialize_public_key(public_key_pem.encode())
    encrypted_aes_key = rsa_encrypt(aes_key, public_key)

    cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
    file_size = 0

    with open(output_path, 'wb') as out_f:
        while True:
            chunk = file_stream.read(CHUNK_SIZE)
            if not chunk:
                break
            file_size += len(chunk)
            encrypted_chunk = cipher.encrypt(chunk)
            out_f.write(encrypted_chunk)

        # Écrire le tag d'authentification à la fin du fichier
        tag = cipher.digest()
        out_f.write(tag)

    return {
        'encrypted_aes_key': encrypted_aes_key,
        'nonce': nonce,
        'tag': tag,
        'file_size': file_size
    }


def decrypt_file_from_storage(encrypted_data: bytes, encrypted_aes_key: bytes, nonce: bytes, private_key) -> bytes:
    """
    Déchiffre un fichier entier en mémoire (pour download/preview).
    Les uploads récents utilisent PyCryptodome (nonce 16 octets) ;
    les anciens fichiers utilisent cryptography AESGCM (nonce 12 octets).
    """
    aes_key = rsa_decrypt(encrypted_aes_key, private_key)

    if len(nonce) == 16:
        from Crypto.Cipher import AES
        if len(encrypted_data) < 16:
            raise ValueError("Données chiffrées trop courtes")
        tag = encrypted_data[-16:]
        ciphertext = encrypted_data[:-16]
        cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aesgcm = AESGCM(aes_key)
    return aesgcm.decrypt(nonce, encrypted_data, None)


def decrypt_file_streaming(input_path: str, encrypted_aes_key: bytes, nonce: bytes, private_key):
    """
    Déchiffre un fichier chiffré en streaming et retourne un générateur de chunks.
    Le tag GCM (16 derniers bytes) est vérifié à la fin.

    Returns:
        generator: chunks déchiffrés à envoyer au client
    """
    from Crypto.Cipher import AES

    aes_key = rsa_decrypt(encrypted_aes_key, private_key)
    cipher = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)

    file_size = os.path.getsize(input_path)
    tag_size = 16
    data_size = file_size - tag_size

    def generate():
        with open(input_path, 'rb') as f:
            bytes_read = 0
            while bytes_read < data_size:
                to_read = min(CHUNK_SIZE, data_size - bytes_read)
                chunk = f.read(to_read)
                if not chunk:
                    break
                bytes_read += len(chunk)
                yield cipher.decrypt(chunk)

            # Lire et vérifier le tag
            tag = f.read(tag_size)
            try:
                cipher.verify(tag)
            except Exception:
                # Tag invalide — fichier corrompu ou modifié
                raise ValueError("Intégrité du fichier compromise : tag GCM invalide")

    return generate()


def generate_encrypted_filename(original_filename: str) -> str:
    """Génère un nom de fichier chiffré unique"""
    unique_id = uuid.uuid4().hex
    return f"{unique_id}.enc"
