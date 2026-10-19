#!/usr/bin/env python3
"""
Script de Migration Automatique - Protection des Métadonnées
(Version non-interactive pour exécution automatisée)
"""

import sqlite3
import os
import shutil
from datetime import datetime

DATABASE_PATH = 'database/cloud.db'
BACKUP_DIR = 'database/backups'


def create_backup():
    """Crée un backup de la base de données."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(BACKUP_DIR, f'cloud_backup_{timestamp}.db')
    shutil.copy2(DATABASE_PATH, backup_path)
    print(f"✅ Backup créé : {backup_path}")
    return backup_path


def check_column_exists(cursor, table, column):
    """Vérifie si une colonne existe."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate_database():
    """Effectue la migration."""
    print("=" * 70)
    print("🔐 MIGRATION BASE DE DONNÉES - Protection Métadonnées (AUTO)")
    print("=" * 70)
    
    if not os.path.exists(DATABASE_PATH):
        print(f"❌ Erreur : Base de données introuvable")
        return False
    
    print(f"\n📁 Base de données : {DATABASE_PATH}")
    db_size_before = os.path.getsize(DATABASE_PATH) / 1024
    print(f"📊 Taille actuelle : {db_size_before:.2f} Ko")
    
    print(f"\n📦 Création backup...")
    backup_path = create_backup()
    
    print(f"\n🔌 Connexion à la base de données...")
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print(f"\n🔍 Vérification colonnes existantes...")
    
    columns_to_add = [
        ('uuid', 'VARCHAR(64)'),  # Pas UNIQUE ici, on l'ajoutera après
        ('encrypted_metadata', 'TEXT'),
        ('metadata_iv', 'VARCHAR(64)'),
        ('metadata_tag', 'VARCHAR(64)'),
        ('encrypted_metadata_key', 'TEXT'),
        ('padded_size', 'BIGINT'),
    ]
    
    columns_added = []
    
    for column_name, column_type in columns_to_add:
        if check_column_exists(cursor, 'files', column_name):
            print(f"   ℹ️  Colonne '{column_name}' existe déjà (skip)")
        else:
            columns_added.append((column_name, column_type))
            print(f"   ➕ Colonne '{column_name}' sera ajoutée")
    
    if not columns_added:
        print(f"\n✅ Toutes les colonnes existent déjà.")
        conn.close()
        return True
    
    print(f"\n🔨 Ajout des colonnes...")
    
    try:
        for column_name, column_type in columns_added:
            sql = f"ALTER TABLE files ADD COLUMN {column_name} {column_type}"
            print(f"   Exécution: ALTER TABLE files ADD COLUMN {column_name}...")
            cursor.execute(sql)
            print(f"   ✅ Colonne '{column_name}' ajoutée")
        
        conn.commit()
        print(f"\n✅ Migration réussie !")
        
    except sqlite3.Error as e:
        print(f"\n❌ Erreur : {e}")
        conn.rollback()
        conn.close()
        shutil.copy2(backup_path, DATABASE_PATH)
        print(f"✅ Base de données restaurée")
        return False
    
    # Statistiques
    cursor.execute("SELECT COUNT(*) FROM files")
    file_count = cursor.fetchone()[0]
    
    conn.close()
    db_size_after = os.path.getsize(DATABASE_PATH) / 1024
    
    print(f"\n📊 Statistiques:")
    print(f"   - Fichiers              : {file_count}")
    print(f"   - Colonnes ajoutées     : {len(columns_added)}")
    print(f"   - Taille avant          : {db_size_before:.2f} Ko")
    print(f"   - Taille après          : {db_size_after:.2f} Ko")
    
    # Schéma final
    print(f"\n📋 Schéma final 'files':")
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(files)")
    columns = cursor.fetchall()
    
    for col in columns:
        col_name, col_type = col[1], col[2]
        print(f"   - {col_name:<30} {col_type}")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("✅ MIGRATION TERMINÉE")
    print("=" * 70)
    
    return True


if __name__ == '__main__':
    success = migrate_database()
    exit(0 if success else 1)
