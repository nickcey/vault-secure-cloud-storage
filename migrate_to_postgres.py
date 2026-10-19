#!/usr/bin/env python3
"""
Script de migration de SQLite vers PostgreSQL pour Vault Secure Cloud Storage
Auteur: Kiro AI
Date: 2026-07-08

Ce script migre toutes les données de la base SQLite vers PostgreSQL
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

# Charger les variables d'environnement depuis .env
load_dotenv()

# Configuration
SQLITE_URI = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'database', 'cloud.db')
POSTGRES_URI = os.environ.get('DATABASE_URL', 'postgresql://vault_user:vault_secure_2026@localhost:5432/vault_db')

def test_postgres_connection():
    """Teste la connexion PostgreSQL"""
    print("🔍 Test de connexion à PostgreSQL...")
    try:
        engine = create_engine(POSTGRES_URI)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.fetchone()[0]
            print(f"✅ PostgreSQL connecté : {version.split(',')[0]}")
            return True
    except Exception as e:
        print(f"❌ Erreur de connexion PostgreSQL : {e}")
        print(f"\n🔧 Vérifiez que :")
        print(f"   1. Docker container 'vault-postgres' est démarré")
        print(f"   2. Le port 5432 est accessible")
        print(f"   3. Les credentials sont corrects")
        return False

def get_table_counts(engine):
    """Compte les enregistrements dans chaque table"""
    tables = ['user', 'file_metadata', 'activity_log', 'active_session', 'payment', 'download_token', 'promo_code', 'shared_link']
    counts = {}
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    for table in tables:
        try:
            result = session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            counts[table] = result.fetchone()[0]
        except:
            counts[table] = 0
    
    session.close()
    return counts

def migrate_data():
    """Migre les données de SQLite vers PostgreSQL"""
    
    print("=" * 70)
    print("🚀 MIGRATION SQLite → PostgreSQL")
    print("=" * 70)
    print()
    
    # 1. Vérifier que SQLite existe
    if not os.path.exists('database/cloud.db'):
        print("❌ Base SQLite introuvable : database/cloud.db")
        print("   Rien à migrer. Création d'une nouvelle base PostgreSQL.")
        return create_fresh_postgres_db()
    
    print(f"✅ Base SQLite trouvée : database/cloud.db")
    sqlite_size = os.path.getsize('database/cloud.db') / 1024
    print(f"   Taille : {sqlite_size:.2f} Ko")
    print()
    
    # 2. Connexion SQLite
    print("🔗 Connexion à SQLite...")
    try:
        sqlite_engine = create_engine(SQLITE_URI)
        sqlite_counts = get_table_counts(sqlite_engine)
        print(f"✅ SQLite connecté")
        print(f"   Données trouvées :")
        for table, count in sqlite_counts.items():
            if count > 0:
                print(f"      • {table}: {count} enregistrement(s)")
        print()
    except Exception as e:
        print(f"❌ Erreur connexion SQLite : {e}")
        return False
    
    # 3. Tester PostgreSQL
    if not test_postgres_connection():
        return False
    print()
    
    # 4. Connexion PostgreSQL
    print("🔗 Connexion à PostgreSQL...")
    try:
        postgres_engine = create_engine(POSTGRES_URI)
        print("✅ PostgreSQL connecté")
        print()
    except Exception as e:
        print(f"❌ Erreur connexion PostgreSQL : {e}")
        return False
    
    # 5. Créer les tables dans PostgreSQL
    print("🏗️  Création des tables PostgreSQL...")
    try:
        # Importer les modèles
        from database.models import db
        from app import app
        
        # Utiliser PostgreSQL
        app.config['SQLALCHEMY_DATABASE_URI'] = POSTGRES_URI
        
        with app.app_context():
            db.create_all()
            print("✅ Tables créées dans PostgreSQL")
            print()
    except Exception as e:
        print(f"❌ Erreur création tables : {e}")
        return False
    
    # 6. Vérifier si PostgreSQL est vide
    postgres_counts = get_table_counts(postgres_engine)
    total_postgres = sum(postgres_counts.values())
    
    if total_postgres > 0:
        print("⚠️  PostgreSQL contient déjà des données !")
        print(f"   Total : {total_postgres} enregistrement(s)")
        response = input("\n   Voulez-vous ÉCRASER ces données ? (oui/non) : ")
        if response.lower() not in ['oui', 'yes', 'o', 'y']:
            print("❌ Migration annulée par l'utilisateur")
            return False
        print()
    
    # 7. Migration table par table
    print("📦 Migration des données...")
    print("-" * 70)
    
    from database.models import User, FileMetadata, ActivityLog, ActiveSession, Payment, DownloadToken, PromoCode, SharedLink
    
    models = [
        ('Utilisateurs', User),
        ('Fichiers', FileMetadata),
        ('Logs d\'activité', ActivityLog),
        ('Sessions actives', ActiveSession),
        ('Paiements', Payment),
        ('Tokens de téléchargement', DownloadToken),
        ('Codes promo', PromoCode),
        ('Liens partagés', SharedLink),
    ]
    
    SqliteSession = sessionmaker(bind=sqlite_engine)
    PostgresSession = sessionmaker(bind=postgres_engine)
    
    sqlite_session = SqliteSession()
    postgres_session = PostgresSession()
    
    total_migrated = 0
    
    try:
        for name, Model in models:
            # Lire depuis SQLite
            records = sqlite_session.query(Model).all()
            
            if len(records) == 0:
                print(f"⏭️  {name}: 0 enregistrement (ignoré)")
                continue
            
            print(f"🔄 {name}: {len(records)} enregistrement(s)...", end=" ")
            
            # Vider la table PostgreSQL si elle contient des données
            postgres_session.query(Model).delete()
            postgres_session.commit()
            
            # Insérer dans PostgreSQL
            migrated = 0
            for record in records:
                try:
                    # Détacher de la session SQLite
                    sqlite_session.expunge(record)
                    
                    # Réinitialiser l'ID pour permettre l'auto-incrémentation
                    record.id = None
                    
                    # Ajouter à PostgreSQL
                    postgres_session.add(record)
                    migrated += 1
                except Exception as e:
                    print(f"\n   ⚠️  Erreur enregistrement {record}: {e}")
                    continue
            
            postgres_session.commit()
            total_migrated += migrated
            print(f"✅ {migrated} migré(s)")
        
        print("-" * 70)
        print(f"\n🎉 Migration terminée avec succès !")
        print(f"   Total migré : {total_migrated} enregistrement(s)")
        print()
        
        # 8. Vérification finale
        print("🔍 Vérification finale...")
        final_counts = get_table_counts(postgres_engine)
        print("   PostgreSQL contient maintenant :")
        for table, count in final_counts.items():
            if count > 0:
                print(f"      • {table}: {count} enregistrement(s)")
        print()
        
        sqlite_session.close()
        postgres_session.close()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Erreur lors de la migration : {e}")
        postgres_session.rollback()
        sqlite_session.close()
        postgres_session.close()
        return False

def create_fresh_postgres_db():
    """Crée une nouvelle base PostgreSQL vide"""
    print("🏗️  Création d'une base PostgreSQL vide...")
    
    if not test_postgres_connection():
        return False
    
    try:
        from database.models import db
        from app import app
        
        app.config['SQLALCHEMY_DATABASE_URI'] = POSTGRES_URI
        
        with app.app_context():
            db.create_all()
            print("✅ Base PostgreSQL créée avec succès")
            return True
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return False

if __name__ == '__main__':
    print()
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║                                                                    ║")
    print("║            🔄 VAULT - Migration SQLite → PostgreSQL               ║")
    print("║                                                                    ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print()
    
    success = migrate_data()
    
    print()
    print("=" * 70)
    if success:
        print("✅ MIGRATION RÉUSSIE !")
        print()
        print("📝 Prochaines étapes :")
        print("   1. Définir DATABASE_URL dans l'environnement :")
        print(f"      export DATABASE_URL=\"{POSTGRES_URI}\"")
        print("   2. Redémarrer l'application Flask")
        print("   3. Tester la connexion et les fonctionnalités")
        print("   4. Optionnel : Sauvegarder database/cloud.db puis le supprimer")
        print()
        print("⚠️  IMPORTANT : Gardez database/cloud.db comme backup pendant quelques jours !")
    else:
        print("❌ MIGRATION ÉCHOUÉE")
        print()
        print("🔧 Dépannage :")
        print("   1. Vérifiez que Docker container 'vault-postgres' est démarré")
        print("   2. Testez la connexion : docker exec -it vault-postgres psql -U vault_user -d vault_db")
        print("   3. Vérifiez les logs : docker logs vault-postgres")
    print("=" * 70)
    print()
    
    sys.exit(0 if success else 1)
