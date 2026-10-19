# 📝 Plan de Modification - Route /upload

**Date :** 8 juillet 2026  
**Objectif :** Intégrer le chiffrement des métadonnées dans la route /upload

---

## 🔍 Code Actuel (Résumé)

```python
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    # 1. Vérifier authentification
    # 2. Calculer espace utilisé
    # 3. Pour chaque fichier :
    #    - Vérifier whitelist extensions
    #    - Vérifier quota
    #    - Chiffrer fichier (encrypt_file_streaming)
    #    - Créer FileMetadata avec :
    #      * filename (CLAIR) ❌
    #      * encrypted_filename (UUID.enc)
    #      * file_size (CLAIR) ❌
    #      * plaintext_size (CLAIR) ❌
    #      * mime_type (CLAIR) ❌
    #    - Sauvegarder en DB
```

---

## ✨ Modifications à Apporter

### 1. Imports Supplémentaires

```python
from modules.metadata_crypto import encrypt_metadata_to_base64, generate_metadata_key
from modules.padding import get_padded_size, add_padding
from modules.key_manager import deserialize_private_key
from cryptography.hazmat.primitives.asymmetric import rsa, padding as rsa_padding
from cryptography.hazmat.primitives import hashes, serialization
import uuid
import secrets
```

### 2. Génération UUID Opaque

**Avant :**
```python
encrypted_filename = generate_encrypted_filename(original_filename)
# Résultat : "a93946c9bd1645e09547b523015738f2.enc"
```

**Après :**
```python
file_uuid = str(uuid.uuid4())  # Génère UUID v4 aléatoire
encrypted_filename = f"{file_uuid}.enc"
# Résultat : "f47ac10b-58cc-4372-a567-0e02b2c3d479.enc"
```

### 3. Création Dictionnaire Métadonnées

**Nouveau code :**
```python
metadata = {
    "filename": original_filename,  # "rapport_2026.pdf"
    "mime_type": file.content_type or 'application/octet-stream',
    "plaintext_size": result['file_size'],  # Taille réelle
    "original_uploaded_at": datetime.utcnow().isoformat()
}
```

### 4. Chiffrement Métadonnées

```python
# Générer clé AES pour métadonnées
metadata_key = generate_metadata_key()  # 32 bytes aléatoires

# Chiffrer métadonnées
encrypted_metadata_b64, metadata_iv_hex, metadata_tag_hex = encrypt_metadata_to_base64(
    metadata, 
    metadata_key
)

# Chiffrer clé métadonnées avec RSA
public_key = serialization.load_pem_public_key(user.public_key.encode('utf-8'))
encrypted_metadata_key = public_key.encrypt(
    metadata_key,
    rsa_padding.OAEP(
        mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
        algorithm=hashes.SHA256(),
        label=None
    )
)
encrypted_metadata_key_b64 = base64.b64encode(encrypted_metadata_key).decode('ascii')
```

### 5. Application du Padding

```python
# Lire fichier chiffré
with open(upload_path, 'rb') as f:
    encrypted_content = f.read()

# Calculer taille paddée
padded_size = get_padded_size(len(encrypted_content))

# Appliquer padding
padded_content = add_padding(encrypted_content, padded_size)

# Réécrire fichier paddé
with open(upload_path, 'wb') as f:
    f.write(padded_content)
```

### 6. Création FileMetadata (Nouveau Schéma)

**Avant :**
```python
file_meta = FileMetadata(
    filename=original_filename,  # ❌ CLAIR
    encrypted_filename=encrypted_filename,
    file_size=result['file_size'],  # ❌ CLAIR
    plaintext_size=result['file_size'],  # ❌ CLAIR
    encrypted_aes_key=result['encrypted_aes_key'].hex(),
    aes_iv=result['nonce'].hex(),
    aes_tag=result['tag'].hex(),
    user_id=user.id,
    mime_type=file.content_type  # ❌ CLAIR
)
```

**Après :**
```python
file_meta = FileMetadata(
    # Ancien schéma (rétrocompatibilité, NULL OK)
    filename=None,  # Plus utilisé
    encrypted_filename=None,  # Remplacé par uuid
    file_size=None,  # Remplacé par padded_size
    plaintext_size=None,  # Déplacé dans encrypted_metadata
    mime_type=None,  # Déplacé dans encrypted_metadata
    
    # Nouveau schéma (chiffré)
    uuid=file_uuid,  # ✅ Opaque
    encrypted_metadata=encrypted_metadata_b64,  # 🔐 Chiffré
    metadata_iv=metadata_iv_hex,
    metadata_tag=metadata_tag_hex,
    encrypted_metadata_key=encrypted_metadata_key_b64,  # 🔐 Chiffré RSA
    padded_size=padded_size,  # 🎭 Obfusqué
    
    # Chiffrement contenu (inchangé)
    encrypted_aes_key=result['encrypted_aes_key'].hex(),
    aes_iv=result['nonce'].hex(),
    aes_tag=result['tag'].hex(),
    
    # Système
    user_id=user.id,
    uploaded_at=datetime.utcnow()
)
```

### 7. Logs d'Activité

**Problème :** Le log stocke le nom du fichier en clair !

```python
activity = ActivityLog(user_id=user_id, action='Upload', filename=original_filename)  # ❌ CLAIR
```

**Solution temporaire :** Utiliser UUID à la place
```python
activity = ActivityLog(user_id=user_id, action='Upload', filename=file_uuid)  # ✅ Opaque
```

**Solution idéale (futur) :** Chiffrer aussi les logs d'activité

---

## 📊 Calcul de l'Espace Utilisé

**Problème :** Le quota doit être calculé sur `padded_size` et non `file_size`

**Avant :**
```python
total_used = sum(f.file_size for f in FileMetadata.query.filter_by(user_id=user.id, is_deleted=False).all())
```

**Après :**
```python
total_used = sum(
    (f.padded_size if f.padded_size else f.file_size)  # Compatibilité anciens fichiers
    for f in FileMetadata.query.filter_by(user_id=user.id, is_deleted=False).all()
)
```

---

## 🔄 Flux Complet Modifié

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Utilisateur upload "rapport.pdf" (2 Mo)                      │
├─────────────────────────────────────────────────────────────────┤
│ 2. Serveur reçoit fichier                                       │
│    - Vérifier whitelist (PDF autorisé ✓)                        │
│    - Vérifier quota (OK ✓)                                      │
├─────────────────────────────────────────────────────────────────┤
│ 3. Chiffrement CONTENU (existant)                               │
│    - encrypt_file_streaming()                                   │
│    - Génère clé AES contenu + chiffre fichier                   │
│    - Résultat : fichier.enc (2.05 Mo)                           │
├─────────────────────────────────────────────────────────────────┤
│ 4. Génération UUID opaque                                       │
│    - uuid = "f47ac10b-58cc-4372-a567-0e02b2c3d479"             │
│    - Nom physique : "f47ac10b-58cc-4372-a567-0e02b2c3d479.enc" │
├─────────────────────────────────────────────────────────────────┤
│ 5. Création métadonnées                                         │
│    - {                                                           │
│        "filename": "rapport.pdf",                               │
│        "mime_type": "application/pdf",                          │
│        "plaintext_size": 2097152,                               │
│        "original_uploaded_at": "2026-07-08T18:30:15.123456Z"   │
│      }                                                           │
├─────────────────────────────────────────────────────────────────┤
│ 6. Chiffrement MÉTADONNÉES                                      │
│    - Générer clé AES métadonnées (32 bytes)                    │
│    - Chiffrer JSON avec AES-256-GCM                             │
│    - Résultat : blob chiffré + IV + tag                         │
├─────────────────────────────────────────────────────────────────┤
│ 7. Chiffrement clé métadonnées                                  │
│    - Chiffrer clé AES avec RSA-2048 (clé publique user)        │
│    - Résultat : clé chiffrée (256 bytes)                        │
├─────────────────────────────────────────────────────────────────┤
│ 8. Application PADDING                                           │
│    - Taille actuelle : 2.05 Mo                                  │
│    - Taille paddée : 4 Mo (palier supérieur)                    │
│    - Ajouter 1.95 Mo de padding aléatoire                       │
│    - Réécrire fichier : "uuid.enc" (4 Mo)                       │
├─────────────────────────────────────────────────────────────────┤
│ 9. Sauvegarde en DB                                              │
│    INSERT INTO files (                                          │
│        uuid,                      -- "f47ac10b-..."            │
│        encrypted_metadata,        -- "QF4uua53mXsu2yW..."      │
│        metadata_iv,               -- "ec1164e18bf1..."         │
│        metadata_tag,              -- "859161b373ea..."         │
│        encrypted_metadata_key,    -- "8a7f3b2e9d4c..."        │
│        padded_size,               -- 4194304 (4 Mo)            │
│        encrypted_aes_key,         -- (contenu)                 │
│        aes_iv,                    -- (contenu)                 │
│        aes_tag,                   -- (contenu)                 │
│        user_id,                                                 │
│        uploaded_at                                              │
│    )                                                            │
├─────────────────────────────────────────────────────────────────┤
│ 10. Log d'activité                                               │
│     ActivityLog(action='Upload', filename=uuid)                 │
├─────────────────────────────────────────────────────────────────┤
│ 11. Redirection dashboard avec message succès                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚠️ Points d'Attention

### 1. Performance

- **Padding ajoute overhead** : 2 Mo → 4 Mo = +100%
- **Relecture fichier** pour appliquer padding (I/O supplémentaire)
- **Chiffrement métadonnées** : Négligeable (~1ms)

**Optimisation future :** Appliquer padding PENDANT le chiffrement streaming

### 2. Rétrocompatibilité

Les anciens fichiers ont :
- `filename` rempli (clair)
- `uuid` NULL
- `padded_size` NULL

Il faut gérer les deux cas dans le dashboard/download.

### 3. Gestion Erreurs

Si le chiffrement métadonnées échoue, il faut :
- Supprimer le fichier physique uploadé
- Ne pas créer l'entrée DB
- Afficher message d'erreur utilisateur

---

## 🧪 Tests à Effectuer

1. ✅ Upload fichier nouveau → Vérifier UUID généré
2. ✅ Vérifier métadonnées chiffrées en DB (pas lisibles)
3. ✅ Vérifier padding appliqué (taille fichier .enc)
4. ✅ Vérifier quota calculé sur padded_size
5. ✅ Upload plusieurs fichiers → Tous avec UUID différents
6. ✅ Fichier bloqué (extension interdite) → Pas de pollution DB
7. ✅ Quota dépassé → Fichier refusé correctement

---

## 📝 Prochaines Étapes

Après modification `/upload` :
1. Modifier `/dashboard` pour déchiffrer métadonnées
2. Modifier `/download` pour supprimer padding
3. Migrer les 5 fichiers existants (script Python)
4. Tests complets upload → dashboard → download

---

**Prêt à implémenter ! 🚀**
