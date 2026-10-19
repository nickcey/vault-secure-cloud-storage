#!/usr/bin/env python3
"""
Script de Migration - Protection des Métadonnées
=================================================

Auteur: Kiro AI
Date: 8 juillet 2026
Objectif: Migrer la table 'files' pour supporter le chiffrement des métadonnées

Ce script ajoute les colonnes nécessaires pour stocker les métadonnées chiffrées :
- uuid : Identifiant opaque (remplace encrypted_filename)
- encrypted_metadata : Métadonnées chiffrées (nom, taille, type, date)
- metadata_iv : Vecteur d'initialisation pour métadonnées
- metadata_tag : Tag d'authentification GCM pour métadonnées
- encrypted_metadata_key : Clé AES métadonnées (chiffrée RSA)
- padded_size : Taille avec padding (obfuscation)

IMPORTANT:
- Ce script est NON-DESTRUCTIF (conserve les données existantes)
- Peut être exécuté plusieurs fois (idempotent)
- Fait un backup automatique avant migration
"""

import sqlite3
import os
import shutil
from datetime import datetime


# ══════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════

DATABASE_PATH = 'database/cloud.db'
BACKUP_DIR = 'database/backups'


def create_backup():
    """
    Crée un backup de la base de données avant migration.
    
    Returns:
        str: Chemin du fichier backup
    """
    # Créer dossier backups si nécessaire
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # Nom du backup avec timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(BACKUP_DIR, f'cloud_backup_{timestamp}.db')
    
    # Copie du fichier
    shutil.copy2(DATABASE_PATH, backup_path)
    
    print(f"✅ Backup créé : {backup_path}")
    return backup_path


def check_column_exists(cursor, table, column):
    """
    Vérifie si une colonne existe dans une table.
    
    Args:
        cursor: Curseur SQLite
        table (str): Nom de la table
        column (str): Nom de la colonne
    
    Returns:
        bool: True si la colonne existe
    """
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def migrate_database():
    """
    Effectue la migration de la base de données.
    """
    print("=" * 70)
    print("🔐 MIGRATION BASE DE DONNÉES - Protection Métadonnées")
    print("=" * 70)
    
    # Vérifier que la DB existe
    if not os.path.exists(DATABASE_PATH):
        print(f"❌ Erreur : Base de données introuvable : {DATABASE_PATH}")
        return False
    
    print(f"\n📁 Base de données : {DATABASE_PATH}")
    
    # Taille avant migration
    db_size_before = os.path.getsize(DATABASE_PATH) / 1024
    print(f"📊 Taille actuelle : {db_size_before:.2f} Ko")
    
    # Backup
    print(f"\n📦 Création backup...")
    backup_path = create_backup()
    
    # Connexion à la base
    print(f"\n🔌 Connexion à la base de données...")
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Vérifier colonnes existantes
    print(f"\n🔍 Vérification colonnes existantes...")
    
    columns_to_add = [
        ('uuid', 'VARCHAR(64) UNIQUE'),
        ('encrypted_metadata', 'TEXT'),
        ('metadata_iv', 'VARCHAR(64)'),
        ('metadata_tag', 'VARCHAR(64)'),
        ('encrypted_metadata_key', 'TEXT'),
        ('padded_size', 'BIGINT'),
    ]
    
    columns_added = []
    columns_existing = []
    
    for column_name, column_type in columns_to_add:
        if check_column_exists(cursor, 'file_metadata', column_name):
            columns_existing.append(column_name)
            print(f"   ℹ️  Colonne '{column_name}' existe déjà (skip)")
        else:
            columns_added.append(column_name)
            print(f"   ➕ Colonne '{column_name}' sera ajoutée")
    
    if not columns_added:
        print(f"\n✅ Toutes les colonnes existent déjà. Migration non nécessaire.")
        conn.close()
        return True
    
    # Migration SQL
    print(f"\n🔨 Ajout des colonnes...")
    
    try:
        for column_name, column_type in columns_to_add:
            if column_name in columns_added:
                sql = f"ALTER TABLE file_metadata ADD COLUMN {column_name} {column_type}"
                print(f"   Exécution: {sql}")
                cursor.execute(sql)
                print(f"   ✅ Colonne '{column_name}' ajoutée")
        
        # Commit
        conn.commit()
        print(f"\n✅ Migration réussie !")
        
    except sqlite3.Error as e:
        print(f"\n❌ Erreur lors de la migration : {e}")
        conn.rollback()
        conn.close()
        
        # Restaurer backup
        print(f"🔄 Restauration du backup...")
        shutil.copy2(backup_path, DATABASE_PATH)
        print(f"✅ Base de données restaurée")
        return False
    
    # Statistiques finales
    print(f"\n📊 Statistiques de migration:")
    
    # Compter fichiers
    cursor.execute("SELECT COUNT(*) FROM file_metadata")
    file_count = cursor.fetchone()[0]
    print(f"   - Fichiers dans la base : {file_count}")
    
    # Colonnes ajoutées
    print(f"   - Colonnes ajoutées     : {len(columns_added)}")
    for col in columns_added:
        print(f"     • {col}")
    
    # Taille après migration
    conn.close()
    db_size_after = os.path.getsize(DATABASE_PATH) / 1024
    print(f"   - Taille avant          : {db_size_before:.2f} Ko")
    print(f"   - Taille après          : {db_size_after:.2f} Ko")
    print(f"   - Différence            : +{db_size_after - db_size_before:.2f} Ko")
    
    # Schéma final
    print(f"\n📋 Schéma final de la table 'file_metadata':")
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(file_metadata)")
    columns = cursor.fetchall()
    
    print(f"\n{'ID':<4} {'Nom Colonne':<30} {'Type':<20} {'Nullable':<10}")
    print("-" * 70)
    for col in columns:
        col_id, col_name, col_type, not_null, default, pk = col
        nullable = "NOT NULL" if not_null else "NULL"
        print(f"{col_id:<4} {col_name:<30} {col_type:<20} {nullable:<10}")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("✅ MIGRATION TERMINÉE AVEC SUCCÈS")
    print("=" * 70)
    print(f"\n💡 Prochaines étapes:")
    print(f"   1. Mettre à jour models.py avec les nouveaux champs")
    print(f"   2. Modifier app.py (routes upload/download)")
    print(f"   3. Migrer les données existantes (chiffrer métadonnées)")
    print(f"\n📁 Backup disponible : {backup_path}")
    
    return True


def verify_migration():
    """
    Vérifie que la migration s'est bien déroulée.
    """
    print("\n🔍 Vérification de la migration...")
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Vérifier que toutes les colonnes existent
    required_columns = ['uuid', 'encrypted_metadata', 'metadata_iv', 
                        'metadata_tag', 'encrypted_metadata_key', 'padded_size']
    
    all_exist = True
    for col in required_columns:
        if not check_column_exists(cursor, 'file_metadata', col):
            print(f"   ❌ Colonne '{col}' manquante")
            all_exist = False
        else:
            print(f"   ✅ Colonne '{col}' présente")
    
    conn.close()
    
    if all_exist:
        print(f"\n✅ Toutes les colonnes requises sont présentes")
        return True
    else:
        print(f"\n❌ Migration incomplète")
        return False


def rollback_migration(backup_path):
    """
    Annule la migration en restaurant le backup.
    
    Args:
        backup_path (str): Chemin du fichier backup
    """
    print(f"\n🔄 Rollback de la migration...")
    
    if not os.path.exists(backup_path):
        print(f"❌ Backup introuvable : {backup_path}")
        return False
    
    shutil.copy2(backup_path, DATABASE_PATH)
    print(f"✅ Base de données restaurée depuis : {backup_path}")
    return True


# ══════════════════════════════════════════════════════════════
# EXECUTION
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import sys
    
    print("\n" + "=" * 70)
    print("  VAULT SECURE CLOUD STORAGE")
    print("  Migration Base de Données - Protection Métadonnées")
    print("=" * 70)
    
    # Confirmation utilisateur
    print(f"\n⚠️  Cette opération va modifier la structure de la base de données.")
    print(f"   Un backup sera créé automatiquement avant toute modification.")
    print(f"\n   Base de données : {DATABASE_PATH}")
    
    response = input(f"\n   Continuer ? (o/n) : ").strip().lower()
    
    if response not in ['o', 'oui', 'y', 'yes']:
        print(f"\n❌ Migration annulée par l'utilisateur.")
        sys.exit(0)
    
    # Exécuter migration
    success = migrate_database()
    
    if success:
        # Vérification
        if verify_migration():
            print(f"\n🎉 Migration réussie et vérifiée !")
            sys.exit(0)
        else:
            print(f"\n❌ Vérification échouée.")
            sys.exit(1)
    else:
        print(f"\n❌ Migration échouée.")
        sys.exit(1)
