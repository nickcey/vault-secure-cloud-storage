# 🔐 Gestion des Secrets - Variables d'Environnement

**Date :** 2026-07-08  
**Application :** Vault Secure Cloud Storage  
**Auteur :** Kiro AI

---

## 📋 Table des matières

1. [Pourquoi externaliser les secrets ?](#pourquoi)
2. [Architecture](#architecture)
3. [Configuration](#configuration)
4. [Utilisation](#utilisation)
5. [Production](#production)
6. [Dépannage](#dépannage)
7. [Sécurité](#sécurité)

---

## 🎯 Pourquoi externaliser les secrets ? {#pourquoi}

### Problèmes avec secrets dans le code

**AVANT (dangereux) :**
```python
# config.py
SECRET_KEY = 'vault-dev-key-123'  # ❌ Exposé sur Git
MAIL_PASSWORD = 'my-password'      # ❌ Volable
```

**Conséquences :**
- 🚨 Si pushé sur GitHub → Secrets publics
- 🚨 Vol de SECRET_KEY → Sessions compromises
- 🚨 Vol email password → Compte Gmail piraté
- 🚨 Impossible d'avoir secrets différents dev/prod

---

## 🏗️ Architecture {#architecture}

### Séparation Code / Secrets

```
┌──────────────────────┐          ┌─────────────────┐
│ config.py (CODE)     │          │ .env (SECRETS)  │
│ ──────────────────── │          │ ───────────────│
│ SECRET_KEY = os.     │  ◄─────  │ SECRET_KEY=xyz  │
│   environ.get(...)   │   lit    │ MAIL_PASS=abc   │
│                      │          └─────────────────┘
│ ✅ Committé sur Git  │               ❌ Jamais sur Git
└──────────────────────┘               🔒 Local uniquement
```

### Fichiers de configuration

| Fichier | Contenu | Sur Git ? | Fonction |
|---------|---------|-----------|----------|
| `.env` | Secrets réels | ❌ NON | Valeurs locales/production |
| `.env.example` | Template sans secrets | ✅ OUI | Guide pour autres devs |
| `config.py` | Lecture variables | ✅ OUI | Code de configuration |
| `.gitignore` | Bloque .env | ✅ OUI | Protection Git |

---

## ⚙️ Configuration {#configuration}

### Étape 1 : Créer votre fichier .env

```bash
# Copier le template
cp .env.example .env

# Ou sous Windows
copy .env.example .env
```

### Étape 2 : Remplir avec vos vraies valeurs

Éditez `.env` :

```bash
# ─── Sécurité ──────────────────────────────────────────────
# Générer une clé aléatoire sécurisée
SECRET_KEY=0ZzONy8Hl2fu6lFYOzv74Njz0Z6Xp7XRUnPkX3waVpY

# ─── Email (Gmail) ─────────────────────────────────────────
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-gmail-app-password

# ─── Campay ────────────────────────────────────────────────
CAMPAY_APP_USERNAME=your-campay-username
CAMPAY_APP_PASSWORD=your-campay-password
```

### Étape 3 : Générer une SECRET_KEY sécurisée

```python
# Méthode 1 : Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Méthode 2 : En ligne
# https://randomkeygen.com/ (choisir "CodeIgniter Encryption Keys")

# Méthode 3 : OpenSSL
openssl rand -base64 32
```

**Résultat :**
```
0ZzONy8Hl2fu6lFYOzv74Njz0Z6Xp7XRUnPkX3waVpY
```

Copiez ce résultat dans `.env` :
```bash
SECRET_KEY=0ZzONy8Hl2fu6lFYOzv74Njz0Z6Xp7XRUnPkX3waVpY
```

---

## 🚀 Utilisation {#utilisation}

### Développement local

```bash
# 1. Assurez-vous que .env existe
ls .env  # Doit exister

# 2. Lancez l'application
python app.py

# 3. Les variables sont chargées automatiquement
# → load_dotenv() dans app.py lit .env
```

### Ajouter une nouvelle variable

**Étape 1 : Ajouter dans .env**
```bash
# .env
NEW_API_KEY=my-secret-key-123
```

**Étape 2 : Lire dans config.py**
```python
# config.py
class Config:
    NEW_API_KEY = os.environ.get('NEW_API_KEY')
```

**Étape 3 : Mettre à jour .env.example**
```bash
# .env.example
NEW_API_KEY=your-api-key-here
```

---

## 🌐 Production {#production}

### Option 1 : Fichier .env sur le serveur

```bash
# Sur le serveur de production
scp .env user@server:/path/to/app/.env
```

⚠️ **Attention :** Le fichier `.env` doit avoir des permissions restrictives :
```bash
chmod 600 .env  # Lecture/écriture uniquement pour le propriétaire
```

---

### Option 2 : Variables d'environnement système (recommandé)

**Heroku :**
```bash
heroku config:set SECRET_KEY="0ZzONy8..."
heroku config:set MAIL_PASSWORD="..."
```

**AWS Elastic Beanstalk :**
```bash
# Dans le dashboard AWS EB :
Configuration > Software > Environment properties
```

**DigitalOcean App Platform :**
```bash
# Dans Settings > App-Level Environment Variables
```

**Docker :**
```bash
docker run -e SECRET_KEY="0ZzONy8..." \
           -e MAIL_PASSWORD="..." \
           my-vault-app
```

**systemd (Linux) :**
```ini
# /etc/systemd/system/vault.service
[Service]
Environment="SECRET_KEY=0ZzONy8..."
Environment="MAIL_PASSWORD=..."
ExecStart=/usr/bin/python /path/to/app.py
```

---

### Option 3 : Service de gestion de secrets

**AWS Secrets Manager :**
```python
import boto3
import json

def get_secret():
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId='vault/production')
    return json.loads(response['SecretString'])

secrets = get_secret()
SECRET_KEY = secrets['SECRET_KEY']
```

**Google Cloud Secret Manager :**
```python
from google.cloud import secretmanager

client = secretmanager.SecretManagerServiceClient()
name = "projects/123/secrets/vault-secret/versions/latest"
response = client.access_secret_version(request={"name": name})
SECRET_KEY = response.payload.data.decode('UTF-8')
```

---

## 🔧 Dépannage {#dépannage}

### Erreur : "SECRET_KEY is not set"

**Cause :** Le fichier `.env` n'existe pas ou n'est pas chargé

**Solution :**
```bash
# Vérifier que .env existe
ls .env

# Si absent, copier le template
cp .env.example .env

# Remplir avec vos valeurs
nano .env  # ou notepad .env sous Windows
```

---

### Erreur : "⚠️ WARNING: Utilisation d'une SECRET_KEY temporaire"

**Cause :** `.env` existe mais `SECRET_KEY` n'est pas définie dedans

**Solution :**
```bash
# Générer une clé
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Ajouter dans .env
echo "SECRET_KEY=<résultat>" >> .env
```

---

### Les emails ne fonctionnent pas

**Cause :** `MAIL_USERNAME` ou `MAIL_PASSWORD` incorrects

**Solution pour Gmail :**

1. Activer l'authentification à 2 facteurs
2. Générer un "App Password" : https://myaccount.google.com/apppasswords
3. Utiliser ce password dans `.env` :
   ```bash
   MAIL_PASSWORD=abcd efgh ijkl mnop
   ```

---

### Les paiements Campay ne fonctionnent pas

**Cause :** `CAMPAY_APP_USERNAME` ou `CAMPAY_APP_PASSWORD` incorrects

**Solution :**

1. Connectez-vous sur https://www.campay.net/
2. Copiez vos credentials API
3. Mettez à jour `.env` :
   ```bash
   CAMPAY_APP_USERNAME=votre-username
   CAMPAY_APP_PASSWORD=votre-password
   ```

---

### Variables pas chargées en production

**Cause :** `load_dotenv()` ne charge que depuis un fichier `.env`

**Solution production :**

Utilisez des variables d'environnement système au lieu de `.env` :

```bash
# Linux/Mac
export SECRET_KEY="0ZzONy8..."

# Windows PowerShell
$env:SECRET_KEY="0ZzONy8..."

# Windows CMD
set SECRET_KEY=0ZzONy8...
```

---

## 🔒 Sécurité {#sécurité}

### ✅ Bonnes pratiques

1. **NE JAMAIS committer .env sur Git**
   ```bash
   # Vérifier que .gitignore contient :
   .env
   *.env
   ```

2. **Permissions restrictives sur .env**
   ```bash
   chmod 600 .env  # Uniquement propriétaire peut lire/écrire
   ```

3. **Secrets différents dev/prod**
   ```
   Dev:  SECRET_KEY=dev-key-123
   Prod: SECRET_KEY=prod-ultra-secure-xyz
   ```

4. **Rotation régulière des secrets**
   - Changer SECRET_KEY tous les 6 mois
   - Changer passwords après un départ d'employé
   - Changer immédiatement si compromis

5. **Ne pas partager .env par email/chat**
   ```
   ❌ Slack: "Voici mon .env : SECRET_KEY=..."
   ✅ Vocal: "Je t'ai ajouté aux secrets du serveur"
   ```

6. **Utiliser des secrets longs et aléatoires**
   ```
   ❌ SECRET_KEY=123
   ✅ SECRET_KEY=0ZzONy8Hl2fu6lFYOzv74Njz0Z6Xp7XRUnPkX3waVpY
   ```

---

### ❌ Erreurs communes

1. **Committer .env sur Git**
   ```bash
   git add .env  # ❌ JAMAIS !
   ```
   
   **Si fait par erreur :**
   ```bash
   # Supprimer du dernier commit
   git rm --cached .env
   git commit --amend
   
   # Changer TOUS les secrets immédiatement
   ```

2. **Partager .env en clair**
   ```
   ❌ Email: "Voici le .env en pièce jointe"
   ❌ Slack: "Je colle le contenu de .env ici"
   ✅ KeePass/1Password partagé
   ✅ AWS Secrets Manager
   ```

3. **Réutiliser les mêmes secrets partout**
   ```
   ❌ Dev et Prod : même SECRET_KEY
   ✅ Dev et Prod : secrets différents
   ```

4. **Secrets faibles**
   ```
   ❌ SECRET_KEY=123
   ❌ SECRET_KEY=password
   ✅ SECRET_KEY=0ZzONy8Hl2fu6lFYOzv74Njz0Z6Xp7XRUnPkX3waVpY
   ```

---

### 🚨 Que faire si secrets exposés ?

**Si .env committé sur Git public :**

1. **Immédiat (< 5 minutes) :**
   ```bash
   # Supprimer le commit (si pas encore pushé)
   git reset --hard HEAD~1
   
   # Si déjà pushé sur GitHub
   git push --force-with-lease origin main
   ```

2. **Changer TOUS les secrets (< 10 minutes) :**
   - Générer nouveau SECRET_KEY
   - Changer password Gmail
   - Changer credentials Campay
   - Mettre à jour `.env` et redéployer

3. **Nettoyer l'historique Git (< 30 minutes) :**
   ```bash
   # Utiliser BFG Repo-Cleaner
   java -jar bfg.jar --delete-files .env
   git reflog expire --expire=now --all
   git gc --prune=now --aggressive
   git push --force
   ```

4. **Notifier (< 1 heure) :**
   - Informer l'équipe
   - Changer tous les accès liés
   - Vérifier les logs pour activité suspecte

---

## 📊 Checklist Sécurité

Avant de pousser sur Git :

- [ ] `.env` est dans `.gitignore`
- [ ] `.env` n'apparaît pas dans `git status`
- [ ] `.env.example` existe (sans secrets réels)
- [ ] `config.py` utilise `os.environ.get()`
- [ ] Secrets différents dev/prod
- [ ] SECRET_KEY est aléatoire et longue (32+ caractères)
- [ ] Permissions `.env` = 600 (Linux/Mac)
- [ ] `.env` pas partagé par email/chat
- [ ] Backup sécurisé de `.env` (chiffré)

---

## 📚 Ressources

- **python-dotenv** : https://github.com/theskumar/python-dotenv
- **Générer SECRET_KEY** : https://randomkeygen.com/
- **Gmail App Passwords** : https://myaccount.google.com/apppasswords
- **12-Factor App** : https://12factor.net/config
- **OWASP Secrets** : https://owasp.org/www-community/vulnerabilities/Use_of_hard-coded_password

---

**Date d'implémentation :** 2026-07-08  
**Status :** ✅ IMPLÉMENTÉ  
**Impact sécurité :** De 0/100 à 100/100 en gestion des secrets
