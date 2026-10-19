#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migration des fichiers existants
Chiffre rétroactivement les métadonnées des fichiers déjà en base
"""

import os
import sys
import json
import uuid
import base64
import shutil
from datetime import datetime

print("="*70)
print("🔄 MIGRATION FICHIERS EXISTANTS")
print("Chiffrement rétroactif des métadonnées")
print("="*70)

# Charger l'application Flask
try:
    from app import app, db
    from database.models import FileMetadata, User
    from modules.metadata_crypto import encrypt_metadata_to_base64, generate_metadata_key
    from modules.padding import get_padded_size, add_padding
    from cryptography.hazmat.primitives import serialization, hashes
    from cryptography.hazmat.primitives.asymmetric import padding as rsa_padding
    
    print("✅ Modules importés avec succès")
except Exception as e:
    print(f"❌ ERREUR import : {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Fonction de migration
def migrate_file(file_meta, user):
    """Migre un fichier vers le nouveau schéma avec métadonnées chiffrées"""
    
    print(f"\n{'='*70}")
    print(f"📁 Fichier ID {file_meta.id} : {file_meta.filename}")
    print(f"{'='*70}")
    
    try:
        # 1. Vérifier si déjà migré
        if file_meta.uuid:
            print("⚠️  Fichier déjà migré (uuid présent), skip")
            return False
        
        # 2. Récupérer métadonnées en clair
        filename = file_meta.filename
        mime_type = file_meta.mime_type or 'application/octet-stream'
        plaintext_size = file_meta.plaintext_size or file_meta.file_size
        uploaded_at = file_meta.uploaded_at.strftime('%Y-%m-%d %H:%M:%S') if file_meta.uploaded_at else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"   📄 Nom : {filename}")
        print(f"   📊 Taille : {plaintext_size} bytes")
        print(f"   🏷️  Type MIME : {mime_type}")
        print(f"   📅 Upload : {uploaded_at}")
        
        # 3. Créer métadonnées JSON
        metadata_dict = {
            'filename': filename,
            'mime_type': mime_type,
            'plaintext_size': plaintext_size,
            'uploaded_at': uploaded_at
        }
        
        # 4. Générer clé métadonnées AES-256
        metadata_key = generate_metadata_key()
        print(f"   🔑 Clé métadonnées AES-256 générée")
        
        # 5. Chiffrer métadonnées
        encrypted_metadata_b64, iv_b64, tag_b64 = encrypt_metadata_to_base64(metadata_dict, metadata_key)
        print(f"   🔐 Métadonnées chiffrées : {encrypted_metadata_b64[:32]}...")
        
        # 6. Récupérer clé publique utilisateur
        public_key_pem = user.public_key.encode('utf-8') if isinstance(user.public_key, str) else user.public_key
        public_key = serialization.load_pem_public_key(public_key_pem)
        
        # 7. Chiffrer clé métadonnées avec RSA
        encrypted_metadata_key = public_key.encrypt(
            metadata_key,
            rsa_padding.OAEP(
                mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        encrypted_metadata_key_b64 = base64.b64encode(encrypted_metadata_key).decode('utf-8')
        print(f"   🔐 Clé métadonnées chiffrée RSA")
        
        # 8. Lire fichier chiffré depuis disque
        old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], file_meta.encrypted_filename)
        
        if not os.path.exists(old_filepath):
            print(f"   ❌ ERREUR : Fichier physique introuvable : {old_filepath}")
            return False
        
        with open(old_filepath, 'rb') as f:
            encrypted_content = f.read()
        
        print(f"   📂 Fichier lu : {len(encrypted_content)} bytes")
        
        # 9. Appliquer padding
        padded_size = get_padded_size(len(encrypted_content))
        padded_content = add_padding(encrypted_content, padded_size)
        print(f"   📏 Padding appliqué : {len(encrypted_content)} → {padded_size} bytes")
        
        # 10. Générer UUID opaque
        file_uuid = str(uuid.uuid4())
        new_filename = f"{file_uuid}.enc"
        new_filepath = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        
        print(f"   🆔 UUID généré : {file_uuid}")
        print(f"   📝 Nouveau nom : {new_filename}")
        
        # 11. Écrire fichier paddé avec nouveau nom
        with open(new_filepath, 'wb') as f:
            f.write(padded_content)
        
        print(f"   💾 Fichier paddé écrit : {new_filepath}")
        
        # 12. Mettre à jour DB
        file_meta.uuid = file_uuid
        file_meta.encrypted_metadata = encrypted_metadata_b64
        file_meta.metadata_iv = iv_b64
        file_meta.metadata_tag = tag_b64
        file_meta.encrypted_metadata_key = encrypted_metadata_key_b64
        file_meta.padded_size = padded_size
        
        db.session.commit()
        print(f"   ✅ DB mise à jour")
        
        # 13. Supprimer ancien fichier
        if os.path.exists(old_filepath):
            os.remove(old_filepath)
            print(f"   🗑️  Ancien fichier supprimé : {file_meta.encrypted_filename}")
        
        print(f"   ✅ MIGRATION RÉUSSIE")
        return True
        
    except Exception as e:
        print(f"   ❌ ERREUR lors de la migration : {e}")
        import traceback
        traceback.print_exc()
        db.session.rollback()
        
        # Rollback fichier si créé
        new_filepath_cleanup = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_uuid}.enc") if 'file_uuid' in locals() else None
        if new_filepath_cleanup and os.path.exists(new_filepath_cleanup):
            os.remove(new_filepath_cleanup)
            print(f"   🔄 Rollback : nouveau fichier supprimé")
        
        return False

# Main
def main():
    with app.app_context():
        print("\n🔍 Recherche fichiers à migrer...")
        
        # Récupérer fichiers avec métadonnées en clair (filename NOT NULL et uuid NULL)
        files_to_migrate = FileMetadata.query.filter(
            FileMetadata.filename.isnot(None),
            FileMetadata.uuid.is_(None),
            FileMetadata.is_deleted == False
        ).all()
        
        print(f"   📊 {len(files_to_migrate)} fichier(s) à migrer trouvé(s)")
        
        if len(files_to_migrate) == 0:
            print("\n✅ Aucun fichier à migrer (tous déjà migrés ou aucun fichier)")
            return
        
        # Demander confirmation
        print(f"\n⚠️  ATTENTION : Cette opération va :")
        print(f"   • Chiffrer les métadonnées de {len(files_to_migrate)} fichier(s)")
        print(f"   • Appliquer padding aux fichiers")
        print(f"   • Renommer les fichiers physiques")
        print(f"   • Mettre à jour la base de données")
        
        # Calculer espace requis
        total_current_size = sum(os.path.getsize(os.path.join(app.config['UPLOAD_FOLDER'], f.encrypted_filename)) if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], f.encrypted_filename)) else 0 for f in files_to_migrate)
        print(f"\n   📊 Taille actuelle totale : {total_current_size / (1024**3):.2f} GB")
        print(f"   ⚠️  Après padding : estimation ~{total_current_size * 1.05 / (1024**3):.2f} GB (+5% approx)")
        
        response = input("\n❓ Continuer ? (oui/non) : ").strip().lower()
        
        if response not in ['oui', 'yes', 'o', 'y']:
            print("\n❌ Migration annulée par l'utilisateur")
            return
        
        # Créer backup DB avant migration
        print("\n📦 Création backup base de données...")
        backup_dir = os.path.join('database', 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        db_path = os.path.join('database', 'cloud.db')
        backup_path = os.path.join(backup_dir, f'cloud_backup_migration_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
        
        shutil.copy2(db_path, backup_path)
        print(f"   ✅ Backup créé : {backup_path}")
        
        # Migrer chaque fichier
        success_count = 0
        failed_count = 0
        
        for file_meta in files_to_migrate:
            # Récupérer utilisateur propriétaire
            user = User.query.get(file_meta.user_id)
            
            if not user:
                print(f"\n❌ Utilisateur introuvable pour fichier ID {file_meta.id}, skip")
                failed_count += 1
                continue
            
            if not user.public_key:
                print(f"\n❌ Clé publique manquante pour utilisateur {user.email}, skip")
                failed_count += 1
                continue
            
            # Migrer
            if migrate_file(file_meta, user):
                success_count += 1
            else:
                failed_count += 1
        
        # Résumé
        print(f"\n{'='*70}")
        print(f"📊 RÉSUMÉ MIGRATION")
        print(f"{'='*70}")
        print(f"   ✅ Réussis  : {success_count}/{len(files_to_migrate)}")
        print(f"   ❌ Échoués  : {failed_count}/{len(files_to_migrate)}")
        print(f"   📦 Backup   : {backup_path}")
        
        if failed_count == 0:
            print(f"\n🎉 MIGRATION TERMINÉE AVEC SUCCÈS !")
        else:
            print(f"\n⚠️  MIGRATION TERMINÉE AVEC ERREURS")
            print(f"   Consultez les logs ci-dessus pour détails")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Migration interrompue par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERREUR FATALE : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
