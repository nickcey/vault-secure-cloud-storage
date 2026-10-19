import sqlite3

conn = sqlite3.connect('database/cloud.db')
cursor = conn.cursor()

# Lister toutes les tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()

print("Tables dans la base de données:")
for table in tables:
    print(f"  - {table[0]}")
    
    # Afficher colonnes de chaque table
    cursor.execute(f"PRAGMA table_info({table[0]})")
    columns = cursor.fetchall()
    print(f"    Colonnes ({len(columns)}):")
    for col in columns[:5]:  # Afficher les 5 premières
        print(f"      • {col[1]} ({col[2]})")
    if len(columns) > 5:
        print(f"      ... et {len(columns) - 5} autres")
    print()

conn.close()
