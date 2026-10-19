"""
Script de correction de sécurité — Suppression des indices de récupération en clair
====================================================================================

Contexte : jusqu'à cette correction, 6 des 12 mots de la phrase mnémonique de
chaque utilisateur étaient stockés en clair dans la base de données (colonne
recovery_hint), pour pré-remplir la page de récupération. Cela réduisait
fortement l'entropie réelle de la récupération pour quiconque a accès à la
base de données (exactement le scénario contre lequel l'architecture
zero-knowledge est censée protéger).

Le code a été corrigé (modules/auth.py, app.py, templates/recover.html) pour
ne plus jamais écrire cet indice. Ce script nettoie les données déjà stockées
pour les comptes existants.

Usage :
    python clear_recovery_hints.py            # affiche ce qui serait fait (dry-run)
    python clear_recovery_hints.py --apply    # applique réellement le nettoyage
"""

import sys
from app import app, db
from database.models import User

DRY_RUN = '--apply' not in sys.argv

with app.app_context():
    users_with_hint = User.query.filter(User.recovery_hint.isnot(None)).all()

    if not users_with_hint:
        print("✅ Aucun utilisateur n'a d'indice de récupération stocké en clair. Rien à faire.")
        sys.exit(0)

    print(f"{'[DRY-RUN] ' if DRY_RUN else ''}{len(users_with_hint)} compte(s) concerné(s) :")
    for user in users_with_hint:
        nb_mots = len(user.recovery_hint.split(',')) if user.recovery_hint else 0
        print(f"  - {user.email} (id={user.id}) : {nb_mots} mot(s) actuellement en clair")

    if DRY_RUN:
        print("\nAucune modification appliquée (mode dry-run).")
        print("Relance avec --apply pour nettoyer réellement ces comptes :")
        print("    python clear_recovery_hints.py --apply")
    else:
        for user in users_with_hint:
            user.recovery_hint = None
        db.session.commit()
        print(f"\n✅ Indice de récupération supprimé pour {len(users_with_hint)} compte(s).")
        print("   La phrase mnémonique complète (12 mots) reste nécessaire pour la récupération,")
        print("   ce qui est le comportement attendu après cette correction de sécurité.")
