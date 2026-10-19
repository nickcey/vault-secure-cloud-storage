"""
reset_database.py — Réinitialise la base de développement Vault.

Les anciens comptes de test ne sont plus compatibles avec le schéma zero-knowledge.
Ce script supprime :
  - la base SQLite (database/cloud.db)
  - le dossier static/uploads (blobs chiffrés)
  - les logs.sessions / fichiers temporaires
Puis recrée les tables avec le nouveau schéma.

Usage :  python reset_database.py
"""

import os
import shutil
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'cloud.db')
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'storage', 'uploads')
LEGACY_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')


def main():
    print('=' * 60)
    print('VAULT — Réinitialisation de la base de développement')
    print('=' * 60)
    print('Cette action supprime TOUS les comptes, fichiers et logs.')
    confirm = input('Confirmer (oui/non) : ').strip().lower()
    if confirm not in ('oui', 'o', 'yes', 'y'):
        print('Annulé.')
        return 0

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f'[+] Supprimé : {DB_PATH}')
    else:
        print(f'[i] Absent : {DB_PATH}')

    for d in (UPLOAD_DIR, LEGACY_UPLOAD_DIR):
        if os.path.isdir(d):
            shutil.rmtree(d)
            print(f'[+] Supprimé : {d}')

    # Recréer le schéma vide
    from app import create_app
    for f in ('app', 'database.models', 'modules.auth'):
        sys.modules.pop(f, None)
    app = create_app()
    print('[+] Tables recréées avec le schéma zero-knowledge.')

    # Création d'un compte admin de test (mot de passe via un PBKDF2 simulé)
    print('[i] Créez un utilisateur admin via "create_admin.py" ou via l\'interface.')
    print('\n✅ Base de développement réinitialisée.')
    print('Démarrez le serveur : python app.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
