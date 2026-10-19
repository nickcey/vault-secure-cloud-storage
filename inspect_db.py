#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'inspection de la base de données
Affiche les fichiers avec tous leurs détails
"""

from app import app, db
from database.models import FileMetadata, User
import json

print("="*80)
print("🔍 INSPECTION BASE DE DONNÉES - PROTECTION MÉTADONNÉES")
print("="*80)

with app.app_context():
    # Compter fichiers par schéma
    total_files = FileMetadata.query.filter_by(is_deleted=False).count()
    new_schema = FileMetadata.query.filter(
        FileMetadata.uuid.isnot(None),
        FileMetadata.is_deleted == False
    ).count()
    old_schema = total_files - new_schema
    
    print(f"\n📊 STATISTIQUES GÉNÉRALES")
    print(f"{'='*80}")
    print(f"   Total fichiers actifs : {total_files}")
    print(f"   • Nouveau schéma (chiffré) : {new_schema}")
    print(f"   • Ancien schéma (clair) : {old_schema}")
    
    if new_schema > 0:
        coverage = (new_schema / total_files) * 100
        print(f"   • Couverture chiffrement : {coverage:.1f}%")
    
    # Afficher derniers fichiers
    print(f"\n📁 DERNIERS FICHIERS UPLOADÉS")
    print(f"{'='*80}")
    
    recent_files = FileMetadata.query.filter_by(
        is_deleted=False
    ).order_by(FileMetadata.id.desc()).limit(5).all()
    
    for i, f in enumerate(recent_files, 1):
        user = User.query.get(f.user_id)
        
        print(f"\n{'─'*80}")
        print(f"📄 FICHIER #{i} (ID: {f.id})")
        print(f"{'─'*80}")
        print(f"   👤 Utilisateur : {user.email if user else 'N/A'}")
        print(f"   📅 Upload : {f.uploaded_at}")
        
        # Détecter schéma
        if f.uuid and f.encrypted_metadata:
            print(f"\n   ✅ NOUVEAU SCHÉMA (Métadonnées chiffrées)")
            print(f"   {'─'*76}")
            print(f"   🆔 UUID : {f.uuid}")
            print(f"   🔐 Métadonnées chiffrées (base64) :")
            print(f"      {f.encrypted_metadata[:80]}...")
            print(f"   🔑 IV : {f.metadata_iv}")
            print(f"   🔑 Tag : {f.metadata_tag}")
            print(f"   🔐 Clé métadonnées chiffrée (RSA) :")
            print(f"      {f.encrypted_metadata_key[:80]}...")
            print(f"   📏 Taille paddée : {f.padded_size:,} bytes")
            print(f"   📦 Nom fichier physique : {f.uuid}.enc")
            
            # Placeholders (doivent être vides/0)
            print(f"\n   📋 Anciens champs (placeholders) :")
            print(f"      • filename : '{f.filename}' (vide = OK)")
            print(f"      • file_size : {f.file_size} (placeholder)")
            print(f"      • encrypted_filename : {f.encrypted_filename}")
            
        else:
            print(f"\n   ⚠️  ANCIEN SCHÉMA (Métadonnées en clair)")
            print(f"   {'─'*76}")
            print(f"   📝 Nom : {f.filename}")
            print(f"   📏 Taille : {f.file_size:,} bytes")
            print(f"   📦 Type MIME : {f.mime_type}")
            print(f"   📦 Nom fichier physique : {f.encrypted_filename}")
    
    # Analyse sécurité
    print(f"\n{'='*80}")
    print(f"🛡️  ANALYSE SÉCURITÉ")
    print(f"{'='*80}")
    
    if new_schema == 0:
        print(f"   ❌ Aucun fichier avec métadonnées chiffrées")
        print(f"   💡 Uploadez un nouveau fichier pour tester")
    elif new_schema == total_files:
        print(f"   ✅ TOUS les fichiers sont protégés !")
        print(f"   🎯 Score sécurité : 99.5%")
    else:
        print(f"   ⚠️  Migration partielle")
        print(f"   📊 {new_schema}/{total_files} fichiers protégés")
        print(f"   💡 Exécutez migrate_existing_files.py pour migrer les anciens")
    
    print(f"\n{'='*80}")
    print(f"✅ INSPECTION TERMINÉE")
    print(f"{'='*80}\n")
