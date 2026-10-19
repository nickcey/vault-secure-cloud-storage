#!/usr/bin/env python3
"""
Script de backup automatique pour Vault Secure Cloud Storage
Auteur: Kiro AI
Date: 2026-07-08

Sauvegarde:
- Base de données SQLite
- Fichiers uploadés (chiffrés) - optionnel
- Configuration (.env.example)
"""

import os
import shutil
import tarfile
from datetime import datetime
import sys

# Configuration
BACKUP_DIR = "backups"
DATABASE_PATH = "database/cloud.db"
UPLOADS_DIR = "static/uploads"
CONFIG_FILES = [".env.example", "config.py"]

def create_backup(include_uploads=False):
    """Crée un backup complet de l'application"""
    
    print("=" * 70)
    print("🔄 BACKUP VAULT SECURE CLOUD STORAGE")
    print("=" * 70)
    print()
    
    # Créer le dossier backups si nécessaire
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"✅ Dossier {BACKUP_DIR}/ créé")
    
    # Timestamp pour nommer le backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"vault_backup_{timestamp}"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    
    # Créer dossier temporaire pour le backup
    os.makedirs(backup_path, exist_ok=True)
    
    print(f"📦 Création du backup : {backup_name}")
    print()
    
    # 1. Backup base de données
    if os.path.exists(DATABASE_PATH):
        db_backup = os.path.join(backup_path, "cloud.db")
        shutil.copy2(DATABASE_PATH, db_backup)
        db_size = os.path.getsize(db_backup) / 1024
        print(f"✅ Base de données sauvegardée ({db_size:.2f} Ko)")
    else:
        print("⚠️  Base de données introuvable")
    
    # 2. Backup fichiers uploadés (optionnel)
    if include_uploads and os.path.exists(UPLOADS_DIR):
        uploads_backup = os.path.join(backup_path, "uploads")
        
        # Compter et copier les fichiers
        files = [f for f in os.listdir(UPLOADS_DIR) if f.endswith('.enc')]
        if files:
            os.makedirs(uploads_backup, exist_ok=True)
            for file in files:
                shutil.copy2(
                    os.path.join(UPLOADS_DIR, file),
                    os.path.join(uploads_backup, file)
                )
            
            # Calculer taille totale
            total_size = sum(
                os.path.getsize(os.path.join(uploads_backup, f)) 
                for f in os.listdir(uploads_backup)
            ) / (1024 * 1024)
            
            print(f"✅ {len(files)} fichiers uploadés sauvegardés ({total_size:.2f} Mo)")
        else:
            print("ℹ️  Aucun fichier uploadé à sauvegarder")
    elif include_uploads:
        print("⚠️  Dossier uploads/ introuvable")
    else:
        print("ℹ️  Fichiers uploadés non inclus (utilisez --with-uploads pour les inclure)")
    
    # 3. Backup configuration
    config_backup = os.path.join(backup_path, "config")
    os.makedirs(config_backup, exist_ok=True)
    
    for config_file in CONFIG_FILES:
        if os.path.exists(config_file):
            shutil.copy2(config_file, os.path.join(config_backup, os.path.basename(config_file)))
    print(f"✅ Configuration sauvegardée")
    
    # 4. Créer archive tar.gz
    print()
    print("🗜️  Compression du backup...")
    archive_name = f"{backup_name}.tar.gz"
    archive_path = os.path.join(BACKUP_DIR, archive_name)
    
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(backup_path, arcname=backup_name)
    
    # Supprimer le dossier temporaire
    shutil.rmtree(backup_path)
    
    # Taille de l'archive
    archive_size = os.path.getsize(archive_path) / (1024 * 1024)
    print(f"✅ Archive créée : {archive_name} ({archive_size:.2f} Mo)")
    print()
    
    # 5. Nettoyage des anciens backups (garder 7 derniers)
    print("🧹 Nettoyage des anciens backups...")
    backups = sorted([
        f for f in os.listdir(BACKUP_DIR) 
        if f.startswith('vault_backup_') and f.endswith('.tar.gz')
    ], reverse=True)
    
    if len(backups) > 7:
        for old_backup in backups[7:]:
            old_path = os.path.join(BACKUP_DIR, old_backup)
            os.remove(old_path)
            print(f"   🗑️  Supprimé : {old_backup}")
    
    print(f"✅ {min(len(backups), 7)} backup(s) conservé(s)")
    print()
    
    print("=" * 70)
    print("✅ BACKUP TERMINÉ AVEC SUCCÈS")
    print("=" * 70)
    print()
    print(f"📁 Emplacement : {archive_path}")
    print(f"💾 Taille : {archive_size:.2f} Mo")
    print()
    
    return archive_path

def restore_backup(backup_file):
    """Restaure un backup"""
    
    print("=" * 70)
    print("🔄 RESTAURATION BACKUP")
    print("=" * 70)
    print()
    
    if not os.path.exists(backup_file):
        print(f"❌ Backup introuvable : {backup_file}")
        return False
    
    print(f"📦 Restauration depuis : {backup_file}")
    print()
    
    # Confirmation
    response = input("⚠️  ATTENTION : Cela va écraser les données actuelles. Continuer ? (oui/non) : ")
    if response.lower() not in ['oui', 'yes', 'o', 'y']:
        print("❌ Restauration annulée")
        return False
    
    # Extraire l'archive
    print("📂 Extraction de l'archive...")
    temp_dir = "temp_restore"
    
    with tarfile.open(backup_file, "r:gz") as tar:
        tar.extractall(temp_dir)
    
    # Trouver le dossier extrait
    extracted = os.listdir(temp_dir)[0]
    extracted_path = os.path.join(temp_dir, extracted)
    
    # Restaurer la base de données
    db_backup = os.path.join(extracted_path, "cloud.db")
    if os.path.exists(db_backup):
        shutil.copy2(db_backup, DATABASE_PATH)
        print("✅ Base de données restaurée")
    
    # Restaurer les uploads
    uploads_backup = os.path.join(extracted_path, "uploads")
    if os.path.exists(uploads_backup):
        if os.path.exists(UPLOADS_DIR):
            shutil.rmtree(UPLOADS_DIR)
        shutil.copytree(uploads_backup, UPLOADS_DIR)
        files_count = len(os.listdir(UPLOADS_DIR))
        print(f"✅ {files_count} fichiers uploadés restaurés")
    
    # Nettoyer
    shutil.rmtree(temp_dir)
    
    print()
    print("=" * 70)
    print("✅ RESTAURATION TERMINÉE")
    print("=" * 70)
    print()
    
    return True

def list_backups():
    """Liste tous les backups disponibles"""
    
    print("=" * 70)
    print("📋 BACKUPS DISPONIBLES")
    print("=" * 70)
    print()
    
    if not os.path.exists(BACKUP_DIR):
        print("ℹ️  Aucun backup trouvé")
        return []
    
    backups = sorted([
        f for f in os.listdir(BACKUP_DIR) 
        if f.startswith('vault_backup_') and f.endswith('.tar.gz')
    ], reverse=True)
    
    if not backups:
        print("ℹ️  Aucun backup trouvé")
        return []
    
    for i, backup in enumerate(backups, 1):
        backup_path = os.path.join(BACKUP_DIR, backup)
        size = os.path.getsize(backup_path) / (1024 * 1024)
        
        # Extraire la date du nom
        date_str = backup.replace('vault_backup_', '').replace('.tar.gz', '')
        date = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
        
        print(f"{i}. {backup}")
        print(f"   📅 Date : {date.strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"   💾 Taille : {size:.2f} Mo")
        print()
    
    return backups

if __name__ == '__main__':
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "restore":
            if len(sys.argv) < 3:
                print("❌ Usage : python backup_vault.py restore <fichier_backup>")
                sys.exit(1)
            restore_backup(sys.argv[2])
        
        elif command == "list":
            list_backups()
        
        elif command == "--with-uploads":
            # Backup complet avec fichiers
            create_backup(include_uploads=True)
        
        else:
            print(f"❌ Commande inconnue : {command}")
            print("Usage :")
            print("  python backup_vault.py                    # Backup léger (DB + config)")
            print("  python backup_vault.py --with-uploads     # Backup complet (+ fichiers)")
            print("  python backup_vault.py list               # Lister les backups")
            print("  python backup_vault.py restore <fichier>  # Restaurer un backup")
    else:
        # Par défaut, créer un backup léger (sans uploads)
        create_backup(include_uploads=False)
