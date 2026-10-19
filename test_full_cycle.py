#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test complet du cycle upload → dashboard → download
Avec chiffrement métadonnées + padding
"""

import os
import sys
import tempfile
import hashlib

print("="*70)
print("🧪 TEST CYCLE COMPLET : Upload → Dashboard → Download")
print("="*70)

# 1. Créer un fichier test
print("\n📁 ÉTAPE 1 : Création fichier test")
test_content = b"Contenu secret de test pour Vault Secure Cloud Storage! \xc3\xa9\xc3\xa7\xc3\xa0"
test_filename = "test_secret_\u00e9\u00e7\u00e0.txt"
original_hash = hashlib.sha256(test_content).hexdigest()
print(f"   ✓ Contenu : {len(test_content)} bytes")
print(f"   ✓ Nom fichier : {test_filename}")
print(f"   ✓ Hash SHA256 : {original_hash[:16]}...")

# 2. Simuler chiffrement métadonnées (comme /upload)
print("\n🔐 ÉTAPE 2 : Simulation chiffrement métadonnées")
try:
    from modules.metadata_crypto import encrypt_metadata_to_base64, decrypt_metadata_from_base64, generate_metadata_key
    from modules.padding import get_padded_size, add_padding, remove_padding
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import rsa, padding as rsa_padding
    import base64
    import uuid
    import json
    
    # Générer UUID opaque
    file_uuid = str(uuid.uuid4())
    print(f"   ✓ UUID généré : {file_uuid}")
    
    # Créer métadonnées JSON
    metadata_dict = {
        'filename': test_filename,
        'mime_type': 'text/plain',
        'plaintext_size': len(test_content),
        'uploaded_at': '2026-07-08 12:00:00'
    }
    print(f"   ✓ Métadonnées : {json.dumps(metadata_dict, ensure_ascii=False)}")
    
    # Générer clé métadonnées AES-256
    metadata_key = generate_metadata_key()
    print(f"   ✓ Clé métadonnées AES-256 générée : {len(metadata_key)} bytes")
    
    # Chiffrer métadonnées
    encrypted_metadata_b64, iv_b64, tag_b64 = encrypt_metadata_to_base64(metadata_dict, metadata_key)
    print(f"   ✓ Métadonnées chiffrées (base64) : {encrypted_metadata_b64[:32]}...")
    print(f"   ✓ IV : {iv_b64[:16]}...")
    print(f"   ✓ Tag : {tag_b64[:16]}...")
    
    # Générer clé RSA test
    print("\n   🔑 Génération clé RSA-2048 test...")
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    
    # Chiffrer clé métadonnées avec RSA
    encrypted_metadata_key = public_key.encrypt(
        metadata_key,
        rsa_padding.OAEP(
            mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    encrypted_metadata_key_b64 = base64.b64encode(encrypted_metadata_key).decode('utf-8')
    print(f"   ✓ Clé métadonnées chiffrée RSA : {len(encrypted_metadata_key)} bytes")
    
    # Simuler chiffrement contenu (simplifié - sans crypto_engine)
    print("\n   🔐 Chiffrement contenu fichier...")
    
    # Générer clé AES contenu
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    content_aes_key = AESGCM.generate_key(bit_length=256)
    
    # Chiffrer contenu avec AES-GCM
    aesgcm = AESGCM(content_aes_key)
    nonce = os.urandom(12)  # 96 bits pour GCM
    encrypted_content = aesgcm.encrypt(nonce, test_content, None)
    print(f"   ✓ Contenu chiffré : {len(encrypted_content)} bytes (original: {len(test_content)})")
    
    # Appliquer padding
    padded_size = get_padded_size(len(encrypted_content))
    padded_encrypted_content = add_padding(encrypted_content, padded_size)
    print(f"   ✓ Taille paddée : {padded_size} bytes (palier)")
    print(f"   ✓ Overhead padding : {(padded_size / len(encrypted_content) - 1) * 100:.1f}%")
    
except Exception as e:
    print(f"   ❌ ERREUR : {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. Simuler déchiffrement métadonnées (comme /dashboard)
print("\n🔓 ÉTAPE 3 : Simulation déchiffrement métadonnées (Dashboard)")
try:
    # Déchiffrer clé métadonnées avec RSA
    metadata_key_decrypted = private_key.decrypt(
        encrypted_metadata_key,
        rsa_padding.OAEP(
            mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    print(f"   ✓ Clé métadonnées déchiffrée : {len(metadata_key_decrypted)} bytes")
    
    # Déchiffrer métadonnées
    metadata_decrypted = decrypt_metadata_from_base64(
        encrypted_metadata_b64,
        iv_b64,
        tag_b64,
        metadata_key_decrypted
    )
    print(f"   ✓ Métadonnées déchiffrées : {json.dumps(metadata_decrypted, ensure_ascii=False)}")
    
    # Vérifier intégrité
    assert metadata_decrypted['filename'] == test_filename, "Filename mismatch!"
    assert metadata_decrypted['plaintext_size'] == len(test_content), "Size mismatch!"
    assert metadata_decrypted['mime_type'] == 'text/plain', "MIME type mismatch!"
    print("   ✅ Intégrité métadonnées OK")
    
except Exception as e:
    print(f"   ❌ ERREUR : {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. Simuler download avec suppression padding
print("\n⬇️  ÉTAPE 4 : Simulation download (suppression padding + déchiffrement)")
try:
    # Supprimer padding
    encrypted_content_unpadded = remove_padding(padded_encrypted_content, len(encrypted_content))
    print(f"   ✓ Padding supprimé : {len(padded_encrypted_content)} → {len(encrypted_content_unpadded)} bytes")
    
    # Vérifier taille
    assert len(encrypted_content_unpadded) == len(encrypted_content), f"Size mismatch after unpadding! {len(encrypted_content_unpadded)} != {len(encrypted_content)}"
    print("   ✅ Taille après unpadding correcte")
    
    # Déchiffrer contenu
    plaintext_decrypted = aesgcm.decrypt(nonce, encrypted_content_unpadded, None)
    print(f"   ✓ Contenu déchiffré : {len(plaintext_decrypted)} bytes")
    
    # Vérifier hash
    recovered_hash = hashlib.sha256(plaintext_decrypted).hexdigest()
    print(f"   ✓ Hash récupéré : {recovered_hash[:16]}...")
    
    assert recovered_hash == original_hash, "Hash mismatch!"
    assert plaintext_decrypted == test_content, "Content mismatch!"
    print("   ✅ Intégrité fichier déchiffré OK")
    
    # Vérifier contenu Unicode
    decoded_text = plaintext_decrypted.decode('utf-8')
    print(f"   ✓ Contenu décodé : \"{decoded_text[:50]}...\"")
    
except Exception as e:
    print(f"   ❌ ERREUR : {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. Résumé
print("\n" + "="*70)
print("✅ TOUS LES TESTS RÉUSSIS !")
print("="*70)
print(f"""
📊 Résumé du cycle complet :
   • Fichier original      : {len(test_content)} bytes
   • Fichier chiffré       : {len(encrypted_content)} bytes (+{len(encrypted_content) - len(test_content)} bytes GCM tag)
   • Fichier paddé         : {padded_size} bytes (palier)
   • Overhead total        : {(padded_size / len(test_content) - 1) * 100:.1f}%
   
🔐 Protection métadonnées :
   • Nom fichier           : Chiffré ✅ (UUID opaque)
   • Type MIME             : Chiffré ✅
   • Taille réelle         : Masquée ✅ (padding)
   • Date upload           : Chiffrée ✅
   
✅ Intégrité vérifiée :
   • Hash SHA256           : {original_hash[:32]}...
   • Contenu récupéré      : Identique à l'original
   • Métadonnées           : Déchiffrées correctement
""")

print("🎉 Le système de chiffrement métadonnées est OPÉRATIONNEL !")
