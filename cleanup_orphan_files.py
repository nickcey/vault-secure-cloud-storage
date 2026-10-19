#!/usr/bin/env python3
"""
Script de nettoyage des fichiers orphelins
Supprime les entrées DB dont les fichiers physiques n'existent plus
"""

import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from database.models import FileMetadata

def cleanup_orphan_files():
    """Nettoie les entrées DB orphelines (sans fichier physique)"""
    
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*70)
        print("🧹 NETTOYAGE DES FICHIERS ORPHELINS")
        print("="*70 + "\n")
        
        # Récupérer tous les fichiers de la DB
        all_files = FileMetadata.query.all()
        
        print(f"📊 Total fichiers dans la base : {len(all_files)}\n")
        
        orphan_files = []
        existing_files = []
        
        for file_meta in all_files:
            # Déterminer le nom du fichier physique
            if file_meta.uuid:
                # Nouveau schéma : UUID.enc
                physical_filename = f"{file_meta.uuid}.enc"
            else:
                # Ancien schéma : encrypted_filename
                physical_filename = file_meta.encrypted_filename
            
            # Chemin complet
            file_path = os.path.join('static', 'uploads', physical_filename)
            
            if os.path.exists(file_path):
                existing_files.append({
                    'id': file_meta.id,
                    'name': file_meta.filename or file_meta.uuid,
                    'path': file_path,
                    'size': os.path.getsize(file_path)
                })
            else:
                orphan_files.append({
                    'id': file_meta.id,
                    'name': file_meta.filename or file_meta.uuid,
                    'path': file_path,
                    'db_size': file_meta.file_size or file_meta.plaintext_size or 0
                })
        
        print(f"✅ Fichiers existants : {len(existing_files)}")
        print(f"❌ Fichiers orphelins  : {len(orphan_files)}\n")
        
        if not orphan_files:
            print("🎉 Aucun fichier orphelin trouvé ! Base de données propre.\n")
            return
        
        # Afficher les orphelins
        print("="*70)
        print("❌ FICHIERS ORPHELINS (entrées DB sans fichier physique)")
        print("="*70 + "\n")
        
        for idx, orphan in enumerate(orphan_files, 1):
            print(f"{idx}. ID {orphan['id']} : {orphan['name']}")
            print(f"   Fichier attendu : {orphan['path']}")
            print(f"   Taille DB       : {orphan['db_size']:,} bytes")
            print()
        
        # Demander confirmation
        print("="*70)
        response = input("❓ Supprimer ces entrées orphelines de la DB ? (oui/non) : ").strip().lower()
        
        if response not in ['oui', 'yes', 'o', 'y']:
            print("\n⚠️  Annulé. Aucune suppression effectuée.\n")
            return
        
        # Créer backup avant suppression
        import shutil
        from datetime import datetime
        
        backup_dir = os.path.join('database', 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backup_dir, f'cloud_backup_cleanup_{timestamp}.db')
        
        db_path = os.path.join('database', 'cloud.db')
        shutil.copy2(db_path, backup_path)
        
        print(f"\n📦 Backup créé : {backup_path}")
        
        # Supprimer les orphelins
        print("\n🗑️  Suppression en cours...\n")
        
        deleted_count = 0
        for orphan in orphan_files:
            try:
                file_meta = FileMetadata.query.get(orphan['id'])
                if file_meta:
                    db.session.delete(file_meta)
                    db.session.commit()
                    print(f"   ✅ Supprimé : ID {orphan['id']} - {orphan['name']}")
                    deleted_count += 1
            except Exception as e:
                print(f"   ❌ Erreur ID {orphan['id']} : {e}")
                db.session.rollback()
        
        print("\n" + "="*70)
        print("📊 RÉSUMÉ")
        print("="*70)
        print(f"   ✅ Supprimés : {deleted_count}/{len(orphan_files)}")
        print(f"   ✅ Restants  : {len(existing_files)}")
        print(f"   📦 Backup    : {backup_path}")
        print("\n✅ Nettoyage terminé !\n")
        
        # Afficher fichiers restants
        if existing_files:
            print("="*70)
            print("✅ FICHIERS VALIDES (avec fichier physique)")
            print("="*70 + "\n")
            
            for idx, existing in enumerate(existing_files, 1):
                size_mb = existing['size'] / (1024 * 1024)
                print(f"{idx}. ID {existing['id']} : {existing['name'][:50]}")
                print(f"   Taille : {size_mb:.2f} MB")
                print()


if __name__ == '__main__':
    try:
        cleanup_orphan_files()
    except KeyboardInterrupt:
        print("\n\n⚠️  Annulé par l'utilisateur.\n")
    except Exception as e:
        print(f"\n❌ Erreur : {e}\n")
        import traceback
        traceback.print_exc()
