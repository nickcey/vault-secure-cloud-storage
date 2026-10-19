#!/usr/bin/env python3
"""
Script d'inspection directe de la base de données
Affiche toutes les colonnes importantes pour vérifier le chiffrement
"""

import sqlite3
import os

# Chemin de la base de données
DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'cloud.db')

def inspect_database():
    """Inspecte la base de données et affiche les métadonnées"""
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Base de données introuvable : {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n" + "="*70)
    print("🔍 INSPECTION DIRECTE DE LA BASE DE DONNÉES")
    print("="*70 + "\n")
    
    # Compter les fichiers
    cursor.execute("SELECT COUNT(*) FROM files")
    total = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM files WHERE uuid IS NOT NULL")
    encrypted = cursor.fetchone()[0]
    
    print(f"📊 STATISTIQUES")
    print(f"   Total fichiers     : {total}")
    print(f"   ✅ Chiffrés         : {encrypted}")
    print(f"   ❌ Non chiffrés     : {total - encrypted}")
    
    print("\n" + "="*70)
    print("📄 LISTE DES FICHIERS (Du plus récent au plus ancien)")
    print("="*70 + "\n")
    
    # Récupérer tous les fichiers
    cursor.execute("""
        SELECT 
            id,
            uuid,
            encrypted_metadata,
            metadata_iv,
            metadata_tag,
            encrypted_metadata_key,
            padded_size,
            filename,
            encrypted_filename,
            file_size,
            plaintext_size,
            mime_type,
            uploaded_at
        FROM files
        ORDER BY id DESC
    """)
    
    files = cursor.fetchall()
    
    if not files:
        print("⚠️  Aucun fichier dans la base de données\n")
        conn.close()
        return
    
    for idx, file_data in enumerate(files, 1):
        (file_id, uuid, encrypted_metadata, metadata_iv, metadata_tag, 
         encrypted_metadata_key, padded_size, filename, encrypted_filename, 
         file_size, plaintext_size, mime_type, uploaded_at) = file_data
        
        print(f"📄 FICHIER #{idx} (ID: {file_id})")
        print("-" * 70)
        
        if uuid:
            # NOUVEAU SCHÉMA
            print(f"   ✅ SCHÉMA : Métadonnées CHIFFRÉES")
            print(f"   🆔 UUID              : {uuid}")
            print(f"   🔐 Métadonnées       : {encrypted_metadata[:60]}...")
            print(f"   🔑 IV                : {metadata_iv}")
            print(f"   🔑 Tag               : {metadata_tag}")
            print(f"   🔑 Clé chiffrée      : {encrypted_metadata_key[:60] if encrypted_metadata_key else 'N/A'}...")
            print(f"   📏 Taille paddée     : {padded_size:,} bytes" if padded_size else "   📏 Taille paddée     : N/A")
            print(f"   📏 Taille réelle     : {plaintext_size:,} bytes" if plaintext_size else "   📏 Taille réelle     : N/A")
            print(f"   📦 Nom physique      : {uuid}.enc")
            print(f"   📋 filename (plc.)   : '{filename}' (devrait être vide)")
            print(f"   📋 file_size (plc.)  : {file_size} (devrait être 0)")
        else:
            # ANCIEN SCHÉMA
            print(f"   ❌ SCHÉMA : Métadonnées NON CHIFFRÉES (ancien)")
            print(f"   📋 Nom VISIBLE       : {filename}")
            print(f"   📏 Taille VISIBLE    : {file_size:,} bytes")
            print(f"   📦 Nom physique      : {encrypted_filename[:40]}..." if encrypted_filename else "N/A")
            print(f"   📦 Type MIME         : {mime_type}")
        
        print(f"   📅 Date upload       : {uploaded_at}")
        print()
    
    print("="*70)
    print("✅ Inspection terminée")
    print("="*70 + "\n")
    
    # Afficher les colonnes de la table
    print("📋 SCHÉMA DE LA TABLE 'files':")
    print("-" * 70)
    cursor.execute("PRAGMA table_info(files)")
    columns = cursor.fetchall()
    for col in columns:
        col_id, col_name, col_type, not_null, default_val, pk = col
        nullable = "NOT NULL" if not_null else "NULLABLE"
        pk_marker = " (PRIMARY KEY)" if pk else ""
        print(f"   {col_name:<25} {col_type:<15} {nullable}{pk_marker}")
    print()
    
    conn.close()


def show_last_file_details():
    """Affiche les détails complets du dernier fichier uploadé"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            id, uuid, encrypted_metadata, metadata_iv, metadata_tag,
            encrypted_metadata_key, padded_size, plaintext_size,
            filename, file_size, uploaded_at
        FROM files
        ORDER BY id DESC
        LIMIT 1
    """)
    
    file_data = cursor.fetchone()
    
    if not file_data:
        print("⚠️  Aucun fichier trouvé\n")
        conn.close()
        return
    
    print("\n" + "="*70)
    print("🔍 DÉTAILS DU DERNIER FICHIER UPLOADÉ")
    print("="*70 + "\n")
    
    (file_id, uuid, encrypted_metadata, metadata_iv, metadata_tag,
     encrypted_metadata_key, padded_size, plaintext_size,
     filename, file_size, uploaded_at) = file_data
    
    if uuid:
        print(f"✅ Métadonnées chiffrées détectées !\n")
        print(f"🆔 UUID                    : {uuid}")
        print(f"📅 Date upload             : {uploaded_at}")
        print()
        print(f"🔐 CHIFFREMENT")
        print(f"   Métadonnées chiffrées   : {encrypted_metadata[:80]}...")
        print(f"   Longueur                : {len(encrypted_metadata)} caractères")
        print(f"   IV (12 bytes hex)       : {metadata_iv}")
        print(f"   Tag (16 bytes hex)      : {metadata_tag}")
        print(f"   Clé chiffrée RSA        : {encrypted_metadata_key[:80] if encrypted_metadata_key else 'N/A'}...")
        print()
        print(f"📏 TAILLES")
        print(f"   Taille paddée           : {padded_size:,} bytes" if padded_size else "   Taille paddée           : N/A")
        print(f"   Taille réelle           : {plaintext_size:,} bytes" if plaintext_size else "   Taille réelle           : N/A")
        if padded_size and plaintext_size:
            overhead = ((padded_size - plaintext_size) / plaintext_size) * 100
            print(f"   Overhead padding        : +{overhead:.1f}%")
        print()
        print(f"📦 ANCIENS CHAMPS (placeholders)")
        print(f"   filename                : '{filename}' (devrait être vide)")
        print(f"   file_size               : {file_size} (devrait être 0)")
    else:
        print(f"❌ Ancien schéma (métadonnées NON chiffrées)\n")
        print(f"📋 Nom visible  : {filename}")
        print(f"📏 Taille       : {file_size:,} bytes")
        print(f"📅 Date         : {uploaded_at}")
    
    print("\n" + "="*70 + "\n")
    
    conn.close()


def show_metadata_sample():
    """Affiche un échantillon de métadonnées chiffrées"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT encrypted_metadata, metadata_iv, metadata_tag
        FROM files
        WHERE uuid IS NOT NULL
        ORDER BY id DESC
        LIMIT 1
    """)
    
    result = cursor.fetchone()
    
    if not result:
        print("⚠️  Aucun fichier avec métadonnées chiffrées trouvé")
        print("💡 Uploadez un nouveau fichier pour tester le chiffrement\n")
        conn.close()
        return
    
    encrypted_metadata, iv, tag = result
    
    print("\n" + "="*70)
    print("🔐 ÉCHANTILLON DE MÉTADONNÉES CHIFFRÉES")
    print("="*70 + "\n")
    
    print(f"📦 Métadonnées chiffrées (base64) :")
    print(f"   {encrypted_metadata}\n")
    
    print(f"🔑 IV (vecteur d'initialisation, 12 bytes hex) :")
    print(f"   {iv}\n")
    
    print(f"🔑 Tag d'authentification (16 bytes hex) :")
    print(f"   {tag}\n")
    
    print("✅ Ces données sont illisibles sans la clé privée de l'utilisateur")
    print("="*70 + "\n")
    
    conn.close()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'last':
            show_last_file_details()
        elif sys.argv[1] == 'sample':
            show_metadata_sample()
        else:
            print("Usage:")
            print("  python inspect_db_direct.py          # Inspection complète")
            print("  python inspect_db_direct.py last     # Détails dernier fichier")
            print("  python inspect_db_direct.py sample   # Échantillon métadonnées chiffrées")
    else:
        inspect_database()
