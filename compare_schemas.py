#!/usr/bin/env python3
"""Comparaison visuelle ancien vs nouveau schéma"""

from app import app, db
from database.models import FileMetadata, User

print("="*80)
print("📊 COMPARAISON ANCIEN vs NOUVEAU SCHÉMA")
print("="*80)

with app.app_context():
    # Anciens fichiers
    old_files = FileMetadata.query.filter(
        FileMetadata.uuid.is_(None),
        FileMetadata.is_deleted == False
    ).limit(3).all()
    
    # Nouveaux fichiers
    new_files = FileMetadata.query.filter(
        FileMetadata.uuid.isnot(None),
        FileMetadata.is_deleted == False
    ).limit(3).all()
    
    print(f"\n{'='*80}")
    print(f"❌ ANCIEN SCHÉMA (Métadonnées EN CLAIR)")
    print(f"{'='*80}\n")
    
    if old_files:
        for f in old_files:
            print(f"ID: {f.id}")
            print(f"  📝 Nom visible : {f.filename}")
            print(f"  📏 Taille visible : {f.file_size:,} bytes")
            print(f"  📦 Type visible : {f.mime_type}")
            print(f"  🗂️  Fichier physique : {f.encrypted_filename}")
            print(f"  🔓 UUID : None (pas de protection)")
            print(f"  🔓 Métadonnées chiffrées : None")
            print(f"  🔴 RISQUE : Admin voit TOUT\n")
    else:
        print("  ✅ Aucun ancien fichier (tous migrés !)\n")
    
    print(f"{'='*80}")
    print(f"✅ NOUVEAU SCHÉMA (Métadonnées CHIFFRÉES)")
    print(f"{'='*80}\n")
    
    if new_files:
        for f in new_files:
            print(f"ID: {f.id}")
            print(f"  🔐 UUID opaque : {f.uuid}")
            print(f"  🔐 Nom chiffré : {f.encrypted_metadata[:40]}... (base64)")
            print(f"  🔐 Taille masquée : {f.padded_size:,} bytes (paddée)")
            print(f"  🔐 Type chiffré : Dans encrypted_metadata")
            print(f"  🗂️  Fichier physique : {f.uuid}.enc")
            print(f"  🟢 SÉCURISÉ : Admin ne voit RIEN\n")
    else:
        print("  ⚠️  Aucun nouveau fichier")
        print("  💡 Uploadez un fichier pour tester\n")
    
    # Score
    total = len(old_files) + len(new_files)
    if total > 0:
        protected = len(new_files)
        score = (protected / total) * 100
        
        print(f"{'='*80}")
        print(f"🎯 SCORE PROTECTION")
        print(f"{'='*80}")
        print(f"   Fichiers protégés : {protected}/{total} ({score:.0f}%)")
        
        if score == 100:
            print(f"   ✅ PARFAIT ! Tous les fichiers sont protégés")
        elif score > 0:
            print(f"   ⚠️  Migration partielle")
            print(f"   💡 Exécutez: python migrate_existing_files.py")
        else:
            print(f"   ❌ Aucun fichier protégé")
            print(f"   💡 Uploadez un nouveau fichier")
    
    print(f"\n{'='*80}\n")
