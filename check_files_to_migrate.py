#!/usr/bin/env python3
"""Vérifier quels fichiers doivent être migrés (sans les modifier)"""

from app import app, db
from database.models import FileMetadata, User

print("🔍 Analyse fichiers à migrer...\n")

with app.app_context():
    # Fichiers avec métadonnées en clair
    files_old = FileMetadata.query.filter(
        FileMetadata.filename.isnot(None),
        FileMetadata.uuid.is_(None),
        FileMetadata.is_deleted == False
    ).all()
    
    # Fichiers déjà migrés
    files_new = FileMetadata.query.filter(
        FileMetadata.uuid.isnot(None),
        FileMetadata.is_deleted == False
    ).all()
    
    print(f"📊 Statistiques :")
    print(f"   • Fichiers ancien schéma (à migrer)  : {len(files_old)}")
    print(f"   • Fichiers nouveau schéma (migrés)   : {len(files_new)}")
    print(f"   • Total fichiers actifs              : {len(files_old) + len(files_new)}")
    
    if files_old:
        print(f"\n📁 Fichiers à migrer :")
        for f in files_old:
            user = User.query.get(f.user_id)
            print(f"   • ID {f.id:3d} | {f.filename:30s} | {f.file_size:10d} bytes | User: {user.email if user else 'N/A'}")
    else:
        print(f"\n✅ Aucun fichier à migrer !")
    
    if files_new:
        print(f"\n✅ Fichiers déjà migrés :")
        for f in files_new:
            print(f"   • ID {f.id:3d} | UUID: {f.uuid} | Padded: {f.padded_size} bytes")
