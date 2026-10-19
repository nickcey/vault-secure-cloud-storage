#!/usr/bin/env python3
"""
Script interactif pour exécuter des requêtes SQL directement sur la BD
"""

import sqlite3
import os
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'cloud.db')

def execute_query(query):
    """Exécute une requête SQL et affiche les résultats"""
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Base de données introuvable : {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute(query)
        results = cursor.fetchall()
        
        # Récupérer les noms de colonnes
        if cursor.description:
            columns = [desc[0] for desc in cursor.description]
            
            # Afficher les résultats
            print("\n" + "="*80)
            print("📊 RÉSULTATS DE LA REQUÊTE")
            print("="*80 + "\n")
            
            # En-têtes
            header = " | ".join(f"{col:<20}" for col in columns)
            print(header)
            print("-" * len(header))
            
            # Lignes
            for row in results:
                row_str = " | ".join(f"{str(val)[:20]:<20}" for val in row)
                print(row_str)
            
            print(f"\n✅ {len(results)} ligne(s) retournée(s)\n")
        else:
            print("\n✅ Requête exécutée avec succès\n")
        
        conn.commit()
        
    except sqlite3.Error as e:
        print(f"\n❌ Erreur SQL : {e}\n")
    
    finally:
        conn.close()


def show_common_queries():
    """Affiche des requêtes SQL courantes"""
    
    print("\n" + "="*80)
    print("📋 REQUÊTES SQL COURANTES")
    print("="*80 + "\n")
    
    queries = {
        "1": ("Voir tous les fichiers (résumé)", 
              "SELECT id, uuid, filename, file_size, padded_size, uploaded_at FROM files ORDER BY id DESC;"),
        
        "2": ("Compter fichiers chiffrés vs non chiffrés",
              "SELECT CASE WHEN uuid IS NOT NULL THEN 'Chiffré' ELSE 'Non chiffré' END as type, COUNT(*) as count FROM files GROUP BY type;"),
        
        "3": ("Dernier fichier uploadé (complet)",
              "SELECT * FROM files ORDER BY id DESC LIMIT 1;"),
        
        "4": ("Fichiers avec métadonnées chiffrées",
              "SELECT id, uuid, LENGTH(encrypted_metadata) as metadata_length, padded_size, plaintext_size FROM files WHERE uuid IS NOT NULL;"),
        
        "5": ("Tous les utilisateurs",
              "SELECT id, username, email, plan, is_suspended FROM users;"),
        
        "6": ("Taille totale par utilisateur",
              "SELECT user_id, SUM(COALESCE(padded_size, file_size)) as total_bytes FROM files GROUP BY user_id;"),
        
        "7": ("Voir schéma table 'files'",
              "PRAGMA table_info(files);"),
        
        "8": ("Derniers 5 fichiers (noms seulement)",
              "SELECT id, COALESCE(uuid, filename) as identifier, uploaded_at FROM files ORDER BY id DESC LIMIT 5;"),
    }
    
    for key, (description, query) in queries.items():
        print(f"{key}. {description}")
        print(f"   {query}")
        print()
    
    print("="*80 + "\n")


def interactive_mode():
    """Mode interactif pour exécuter des requêtes"""
    
    print("\n" + "="*80)
    print("🔍 MODE INTERACTIF - REQUÊTES SQL")
    print("="*80)
    print("\nTapez 'help' pour voir les requêtes courantes")
    print("Tapez 'exit' ou 'quit' pour quitter")
    print("Tapez directement une requête SQL pour l'exécuter\n")
    
    queries = {
        "1": "SELECT id, uuid, filename, file_size, padded_size, uploaded_at FROM files ORDER BY id DESC;",
        "2": "SELECT CASE WHEN uuid IS NOT NULL THEN 'Chiffré' ELSE 'Non chiffré' END as type, COUNT(*) as count FROM files GROUP BY type;",
        "3": "SELECT * FROM files ORDER BY id DESC LIMIT 1;",
        "4": "SELECT id, uuid, LENGTH(encrypted_metadata) as metadata_length, padded_size, plaintext_size FROM files WHERE uuid IS NOT NULL;",
        "5": "SELECT id, username, email, plan, is_suspended FROM users;",
        "6": "SELECT user_id, SUM(COALESCE(padded_size, file_size)) as total_bytes FROM files GROUP BY user_id;",
        "7": "PRAGMA table_info(files);",
        "8": "SELECT id, COALESCE(uuid, filename) as identifier, uploaded_at FROM files ORDER BY id DESC LIMIT 5;",
    }
    
    while True:
        try:
            user_input = input("SQL> ").strip()
            
            if user_input.lower() in ['exit', 'quit', 'q']:
                print("\n👋 Au revoir !\n")
                break
            
            if user_input.lower() in ['help', 'h', '?']:
                show_common_queries()
                continue
            
            if not user_input:
                continue
            
            # Si c'est un numéro, exécuter la requête correspondante
            if user_input in queries:
                query = queries[user_input]
                print(f"\n📝 Exécution : {query}\n")
                execute_query(query)
            else:
                # Sinon, exécuter la requête directement
                execute_query(user_input)
        
        except KeyboardInterrupt:
            print("\n\n👋 Au revoir !\n")
            break
        except Exception as e:
            print(f"\n❌ Erreur : {e}\n")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Exécuter la requête passée en argument
        query = ' '.join(sys.argv[1:])
        execute_query(query)
    else:
        # Mode interactif
        interactive_mode()
