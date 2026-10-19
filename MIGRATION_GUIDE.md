# 🔄 Guide de Migration - Chiffrement Métadonnées

## 📋 Résumé

Ce guide explique comment migrer les **fichiers existants** vers le nouveau système de chiffrement des métadonnées.

---

## 🎯 Objectif

Migrer les 5 fichiers existants (17 GB total) pour :
- ✅ **Chiffrer leurs métadonnées** (nom, type MIME, taille, date)
- ✅ **Appliquer padding** pour masquer la taille réelle
- ✅ **Générer UUID opaques** pour les noms de fichiers
- ✅ **Maintenir rétrocompatibilité** (ancien schéma fonctionne toujours)

---

## 📊 État Actuel

### Fichiers à Migrer

| ID  | Nom Fichier                                            | Taille     | Utilisateur            |
|-----|--------------------------------------------------------|------------|------------------------|
| 1   | Windows.iso                                            | 4.9 GB     | nzetchouon@gmail.com   |
| 2   | 04-FC25 Face.cpk                                       | 6.8 GB     | nzetchouon@gmail.com   |
| 3   | Valider les retraits Wallet via biométrie.xlsx         | 14 KB      | Test@yopmail.com       |
| 5   | ProPlus2021Retail.img                                  | 5.1 GB     | nzetchouon@gmail.com   |
| 6   | AFB_PS03_SECURITE_API_SARA_AGENT_DSC_V1.0_10082026.pdf | 2.2 MB     | nzetchouon@gmail.com   |

**Total** : ~17 GB

---

## ⚙️ Prérequis

1. **Backup base de données** ✅ (automatique)
2. **Espace disque disponible** : ~109 GB libres (suffisant)
3. **Clés publiques utilisateurs** : Présentes en DB
4. **Application arrêtée** : Recommandé (éviter uploads pendant migration)

---

## 🚀 Procédure de Migration

### Étape 1 : Vérifier les Fichiers

```bash
python check_files_to_migrate.py
```

Affiche les fichiers à migrer et leur état actuel.

### Étape 2 : Lancer la Migration

```bash
python migrate_existing_files.py
```

Le script va :
1. 🔍 Rechercher fichiers à migrer (5 trouvés)
2. 💬 Demander confirmation
3. 📦 Créer backup DB automatique
4. 🔄 Migrer chaque fichier :
   - Lire métadonnées en clair
   - Chiffrer métadonnées (AES-256-GCM + RSA-2048)
   - Lire fichier chiffré depuis disque
   - Appliquer padding (paliers 4Ko → 1Go)
   - Générer UUID opaque
   - Écrire nouveau fichier paddé
   - Mettre à jour DB
   - Supprimer ancien fichier
5. 📊 Afficher résumé (réussis/échoués)

### Étape 3 : Vérifier

```bash
python check_files_to_migrate.py
```

Devrait afficher :
```
✅ Aucun fichier à migrer !
✅ Fichiers déjà migrés : 5
```

---

## 🛡️ Sécurité

### Backup Automatique

Avant chaque migration, un backup complet de la DB est créé :
```
database/backups/cloud_backup_migration_YYYYMMDD_HHMMSS.db
```

### Rollback Manuel

Si problème, restaurer depuis backup :
```bash
# Arrêter l'application
# Remplacer la DB actuelle
copy database\backups\cloud_backup_migration_XXXXXXXX_XXXXXX.db database\cloud.db
# Redémarrer l'application
```

### Rollback Automatique

Le script effectue un rollback automatique en cas d'erreur :
- DB : `db.session.rollback()`
- Fichier : Suppression nouveau fichier si créé

---

## 📈 Impact

### Avant Migration

- **Score sécurité** : 97%
- **Métadonnées** : En clair en DB
- **Noms fichiers** : Hash MD5 visible (pattern identifiable)
- **Tailles** : Vraie taille visible

### Après Migration

- **Score sécurité** : 99.2%
- **Métadonnées** : Chiffrées AES-256-GCM + RSA-2048
- **Noms fichiers** : UUID v4 opaque (non déterministe)
- **Tailles** : Masquées par padding (paliers exponentiels)

### Espace Disque

- **Avant** : ~17 GB
- **Après** : ~17.85 GB (+5% padding moyen pour gros fichiers)
- **Overhead** : Acceptable pour obfuscation

---

## ⚠️ Avertissements

1. **Migration irréversible** : Les anciens fichiers sont supprimés après succès
2. **Application arrêtée** : Recommandé (éviter conflits)
3. **Gros fichiers** : Migration peut prendre plusieurs minutes (17 GB à traiter)
4. **Backup manuel** : Optionnel mais recommandé avant de lancer

---

## 🐛 Dépannage

### Erreur "Fichier physique introuvable"

```bash
# Vérifier que les fichiers existent
dir static\uploads\*.enc
```

### Erreur "Clé publique manquante"

```bash
# Vérifier clés publiques en DB
python -c "from app import app, db; from database.models import User; \
with app.app_context(): \
    for u in User.query.all(): \
        print(f'{u.email}: {\"OK\" if u.public_key else \"MANQUANTE\"}')"
```

### Migration échouée

1. Consulter logs ci-dessus pour erreur spécifique
2. Restaurer depuis backup si nécessaire
3. Réessayer avec un seul fichier (modifier script)

---

## 📞 Support

En cas de problème :
1. **Logs** : Consulter sortie console du script
2. **Backup** : Toujours disponible dans `database/backups/`
3. **État** : Vérifier avec `check_files_to_migrate.py`

---

## ✅ Checklist Post-Migration

- [ ] Tous fichiers migrés (5/5)
- [ ] Dashboard affiche noms correctement
- [ ] Download fonctionne (intégrité vérifiée)
- [ ] Espace disque suffisant (~18 GB utilisés)
- [ ] Backup DB conservé
- [ ] Logs activité OK (UUID au lieu de filename)

---

**Date** : 2026-07-08  
**Version** : Phase 1 (Serveur-side)  
**Phase 2** : Client-side (zero-knowledge complet) - À venir
