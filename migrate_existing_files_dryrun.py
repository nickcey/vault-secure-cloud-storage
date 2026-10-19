#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DRY RUN - Simulation migration sans modifications
"""

from app import app, db
from database.models import FileMetadata, User
from modules.padding import get_padded_size
import os

print("🔍 DRY RUN - Simulation Migration (AUCUNE MODIFICATION)\n")

with app.app_context():
    files = FileMetadata.query.filter(
        FileMetadata.filename.isnot(None),
        FileMetadata.uuid.is_(None),
        FileMetadata.is_deleted == False
    ).all()
    
    print(f"📊 {len(files)} fichier(s) à migrer\n")
    
    total_current = 0
    total_padded = 0
    
    for f in files:
        user = User.query.get(f.user_id)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f.encrypted_filename)
        
        if os.path.exists(filepath):
            current_size = os.path.getsize(filepath)
            padded_size = get_padded_size(current_size)
            overhead = (padded_size / current_size - 1) * 100
            
            total_current += current_size
            total_padded += padded_size
            
            print(f"{'='*70}")
            print(f"📁 {f.filename[:50]}")
            print(f"   User       : {user.email if user else 'N/A'}")
            print(f"   Taille actuelle : {current_size:>12,} bytes ({current_size / (1024**3):.2f} GB)")
            print(f"   Taille paddée   : {padded_size:>12,} bytes ({padded_size / (1024**3):.2f} GB)")
            print(f"   Overhead        : {overhead:>12.1f}%")
            print(f"   UUID généré     : (simulation)")
        else:
            print(f"⚠️  Fichier manquant : {f.encrypted_filename}")
    
    print(f"\n{'='*70}")
    print(f"📊 RÉSUMÉ SIMULATION")
    print(f"{'='*70}")
    print(f"   Taille actuelle totale : {total_current:>12,} bytes ({total_current / (1024**3):.2f} GB)")
    print(f"   Taille après padding   : {total_padded:>12,} bytes ({total_padded / (1024**3):.2f} GB)")
    print(f"   Overhead total         : {(total_padded / total_current - 1) * 100:.2f}%")
    print(f"   Espace supplémentaire  : {(total_padded - total_current) / (1024**3):.2f} GB")
    print(f"\n✅ Simulation terminée (AUCUNE modification apportée)")
