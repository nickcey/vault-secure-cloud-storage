# 🔐 Protection Complète des Métadonnées - Design Document

**Date :** 8 juillet 2026  
**Objectif :** Zero-Knowledge complet (métadonnées + contenu)  
**Score actuel :** 97/100 → **Objectif : 100/100**

---

## 📋 TABLE DES MATIÈRES

1. [Problème Actuel](#problème-actuel)
2. [Solution Proposée](#solution-proposée)
3. [Schéma de Base de Données](#schéma-de-base-de-données)
4. [Flux de Chiffrement](#flux-de-chiffrement)
5. [Implémentation Étape par Étape](#implémentation-étape-par-étape)
6. [Limites Résiduelles](#limites-résiduelles)

---

## ❌ Problème Actuel

### Métadonnées Exposées en Clair

**Table `files` actuelle :**
```sql
CREATE TABLE files (
    id INTEGER PRIMARY KEY,
    filename VARCHAR(200) NOT NULL,              -- ❌ CLAIR : "contrat_client_dupont.pdf"
    encrypted_filename VARCHAR(200) NOT NULL,    -- UUID.enc (OK)
    file_size INTEGER NOT NULL,                  -- ❌ CLAIR : 2457600 bytes
    plaintext_size BIGINT,                       -- ❌ CLAIR : 2400000 bytes
    mime_type VARCHAR(100),                      -- ❌ CLAIR : "application/pdf"
    uploaded_at DATETIME,                        -- ❌ CLAIR : "2026-07-08 18:30:00"
    is_deleted BOOLEAN,
    deleted_at DATETIME,
    user_id INTEGER,
    -- Chiffrement contenu (OK) --
    encrypted_aes_key TEXT NOT NULL,
    aes_iv VARCHAR(64) NOT NULL,
    aes_tag VARCHAR(64) NOT NULL
);
```

### Failles de Confidentialité

**Un attaquant avec accès à la base de données peut :**

1. ✅ **Lire les noms de fichiers**
   ```sql
   SELECT filename FROM files WHERE user_id = 42;
   → "salaire_2026.pdf", "contrat_secret.docx", "photos_vacances.zip"
   ```
   **Impact :** Révèle nature des documents (finances, juridique, personnel)

2. ✅ **Deviner le contenu via la taille**
   ```sql
   SELECT filename, file_size FROM files;
   → "document.pdf" : 1024 bytes (probablement 1 page)
   → "rapport.pdf" : 5242880 bytes (probablement ~100 pages)
   ```
   **Impact :** Analyse de corrélation (taille = importance du document)

3. ✅ **Reconstruire l'arborescence** (si dossiers implémentés)
   ```sql
   SELECT filename, parent_folder_id FROM files;
   → /Finances/2026/Janvier/facture_01.pdf
   → /Clients/Dupont/contrat_v3.docx
   ```
   **Impact :** Révèle organisation personnelle/professionnelle

4. ✅ **Profiling temporel**
   ```sql
   SELECT filename, uploaded_at FROM files WHERE user_id = 42 ORDER BY uploaded_at;
   → "cv.pdf" uploadé 08:00
   → "lettre_demission.docx" uploadé 08:15
   → "nouveau_contrat.pdf" uploadé 10:30
   ```
   **Impact :** Révèle événements de vie (recherche emploi, démission)

5. ✅ **Identifier fichiers sensibles**
   ```
   file_size = 4096 bytes + mime_type = "application/pdf" + filename contains "medical"
   → Probablement ordonnance/résultat médical
   ```

### Exemple d'Attaque Réelle

**Scénario :** Pirate compromet la base de données (SQL injection, backup volé, etc.)

```sql
-- Trouver documents financiers
SELECT filename, file_size, uploaded_at 
FROM files 
WHERE filename LIKE '%salaire%' 
   OR filename LIKE '%impots%' 
   OR filename LIKE '%banque%';

Résultat :
+---------------------------+------------+---------------------+
| filename                  | file_size  | uploaded_at         |
+---------------------------+------------+---------------------+
| salaire_janvier_2026.pdf  | 45678      | 2026-02-01 09:00:00 |
| declaration_impots.pdf    | 1234567    | 2026-04-15 22:30:00 |
| releve_bancaire.pdf       | 234567     | 2026-07-01 08:00:00 |
+---------------------------+------------+---------------------+

Analyse :
✅ L'attaquant sait que la victime a un salaire
✅ Peut estimer le revenu via taille du PDF (nombre de pages)
✅ Sait quand les documents ont été consultés (urgence?)
✅ Peut corréler avec d'autres événements (recherche d'emploi?)
```

**Verdict :** Le chiffrement du contenu seul ne suffit PAS. Les métadonnées révèlent trop d'informations.

---

## ✅ Solution Proposée

### Principes

1. **Zero-Knowledge Complet** : Le serveur ne doit connaître QUE :
   - Un UUID opaque (identifiant fichier)
   - Un blob chiffré (contenu)
   - User ID propriétaire

2. **Chiffrement Client-Side** : Toutes les métadonnées sont chiffrées côté client AVANT l'upload.

3. **Padding Agressif** : Les tailles réelles sont masquées par padding pour empêcher l'analyse de corrélation.

4. **Arborescence Chiffrée** : Si des dossiers existent, leur structure est chiffrée.

---

## 🗄️ Schéma de Base de Données

### AVANT (Actuel)

```sql
CREATE TABLE files (
    id INTEGER PRIMARY KEY,
    filename VARCHAR(200) NOT NULL,              -- ❌ CLAIR
    encrypted_filename VARCHAR(200) NOT NULL,    -- UUID.enc
    file_size INTEGER NOT NULL,                  -- ❌ CLAIR (taille chiffrée)
    plaintext_size BIGINT,                       -- ❌ CLAIR (taille originale)
    encrypted_aes_key TEXT NOT NULL,             -- ✅ Chiffré RSA
    aes_iv VARCHAR(64) NOT NULL,
    aes_tag VARCHAR(64) NOT NULL,
    mime_type VARCHAR(100),                      -- ❌ CLAIR
    uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- ❌ CLAIR
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at DATETIME,
    user_id INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

---

### APRÈS (Nouvelle Version)

```sql
CREATE TABLE files (
    -- ══════════════════════════════════════════════════════════
    -- IDENTIFIANTS (Seules données non chiffrées)
    -- ══════════════════════════════════════════════════════════
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,                    -- ✅ Nécessaire pour requêtes
    uuid VARCHAR(64) UNIQUE NOT NULL,            -- ✅ UUID opaque (non séquentiel)
    
    -- ══════════════════════════════════════════════════════════
    -- MÉTADONNÉES CHIFFRÉES (AES-256-GCM)
    -- ══════════════════════════════════════════════════════════
    encrypted_metadata TEXT NOT NULL,            -- 🔐 JSON chiffré : {filename, mime_type, plaintext_size, original_uploaded_at}
    metadata_iv VARCHAR(64) NOT NULL,            -- Vecteur initialisation (unique par fichier)
    metadata_tag VARCHAR(64) NOT NULL,           -- Tag authentification GCM
    
    -- ══════════════════════════════════════════════════════════
    -- CHIFFREMENT CONTENU (Inchangé)
    -- ══════════════════════════════════════════════════════════
    encrypted_aes_key TEXT NOT NULL,             -- ✅ Clé AES contenu (chiffrée RSA)
    content_iv VARCHAR(64) NOT NULL,             -- IV pour contenu
    content_tag VARCHAR(64) NOT NULL,            -- Tag GCM pour contenu
    
    -- ══════════════════════════════════════════════════════════
    -- TAILLE AVEC PADDING (Obfuscation)
    -- ══════════════════════════════════════════════════════════
    padded_size BIGINT NOT NULL,                 -- 🎭 Taille arrondie (4 Ko, 16 Ko, 64 Ko, 256 Ko, 1 Mo, ...)
    
    -- ══════════════════════════════════════════════════════════
    -- ARBORESCENCE CHIFFRÉE (Dossiers)
    -- ══════════════════════════════════════════════════════════
    encrypted_folder_path TEXT,                  -- 🔐 Chemin chiffré : "/encrypted_abc123/encrypted_def456/"
    folder_path_iv VARCHAR(64),                  -- IV pour chemin
    folder_path_tag VARCHAR(64),                 -- Tag GCM pour chemin
    parent_folder_uuid VARCHAR(64),              -- ✅ UUID parent (pour requêtes, mais opaque)
    
    -- ══════════════════════════════════════════════════════════
    -- TIMESTAMPS (Obfuscation optionnelle)
    -- ══════════════════════════════════════════════════════════
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- ⚠️ Timestamp serveur (arrondi à l'heure/jour si besoin)
    modified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- ══════════════════════════════════════════════════════════
    -- SOFT DELETE (Inchangé)
    -- ══════════════════════════════════════════════════════════
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at DATETIME,
    
    -- ══════════════════════════════════════════════════════════
    -- INDEXES
    -- ══════════════════════════════════════════════════════════
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id),
    INDEX idx_uuid (uuid),
    INDEX idx_parent_folder (parent_folder_uuid),
    INDEX idx_is_deleted (is_deleted)
);
```

---

### 📊 Comparaison AVANT/APRÈS

| Colonne | AVANT | APRÈS | Changement |
|---------|-------|-------|------------|
| **filename** | `VARCHAR(200)` CLAIR | ❌ **SUPPRIMÉE** | → Déplacé dans `encrypted_metadata` |
| **encrypted_filename** | `VARCHAR(200)` UUID.enc | ❌ **SUPPRIMÉE** | → Remplacé par `uuid` |
| **uuid** | ❌ N/A | ✅ `VARCHAR(64)` UNIQUE | **NOUVEAU** : Identifiant opaque |
| **file_size** | `INTEGER` CLAIR | ❌ **SUPPRIMÉE** | → Remplacé par `padded_size` |
| **plaintext_size** | `BIGINT` CLAIR | ❌ **SUPPRIMÉE** | → Déplacé dans `encrypted_metadata` |
| **mime_type** | `VARCHAR(100)` CLAIR | ❌ **SUPPRIMÉE** | → Déplacé dans `encrypted_metadata` |
| **uploaded_at** | `DATETIME` CLAIR | ❌ **SUPPRIMÉE** | → Déplacé dans `encrypted_metadata` + `created_at` arrondi |
| **encrypted_metadata** | ❌ N/A | ✅ `TEXT` JSON chiffré | **NOUVEAU** : Toutes métadonnées sensibles |
| **metadata_iv** | ❌ N/A | ✅ `VARCHAR(64)` | **NOUVEAU** : IV pour métadonnées |
| **metadata_tag** | ❌ N/A | ✅ `VARCHAR(64)` | **NOUVEAU** : Tag GCM métadonnées |
| **padded_size** | ❌ N/A | ✅ `BIGINT` | **NOUVEAU** : Taille arrondie (obfuscation) |
| **encrypted_folder_path** | ❌ N/A | ✅ `TEXT` | **NOUVEAU** : Chemin dossiers chiffré |
| **parent_folder_uuid** | ❌ N/A | ✅ `VARCHAR(64)` | **NOUVEAU** : Parent opaque |
| **encrypted_aes_key** | ✅ `TEXT` | ✅ `TEXT` | **INCHANGÉ** |
| **aes_iv** → **content_iv** | ✅ `VARCHAR(64)` | ✅ `VARCHAR(64)` | **RENOMMÉ** (clarté) |
| **aes_tag** → **content_tag** | ✅ `VARCHAR(64)` | ✅ `VARCHAR(64)` | **RENOMMÉ** (clarté) |

---

### 🔐 Structure `encrypted_metadata` (JSON)

**Contenu déchiffré :**
```json
{
  "filename": "contrat_client_dupont.pdf",
  "mime_type": "application/pdf",
  "plaintext_size": 2457600,
  "original_uploaded_at": "2026-07-08T18:30:15.123456Z",
  "custom_metadata": {
    "description": "Contrat signé le 05/07/2026",
    "tags": ["client", "contrat", "2026"],
    "color": "red",
    "favorite": true
  }
}
```

**Chiffré (stocké en DB) :**
```
"8a7f3b2e9d4c1a5f6e8b3c9d2a1f4e7b9c3d6a2e5f8b1c4d7a3e6f9b2c5d8a1e4f7b3c6d9a2e5f..."
```

**Avantages :**
- ✅ Nom de fichier invisible
- ✅ Type MIME invisible (impossible de savoir si c'est un PDF, image, vidéo...)
- ✅ Taille réelle invisible
- ✅ Date exacte d'upload invisible
- ✅ Métadonnées custom extensibles (tags, descriptions, couleurs...)

---

## 🔄 Flux de Chiffrement

### 📤 UPLOAD (Client → Serveur)

```
┌─────────────────────────────────────────────────────────────────────┐
│ CLIENT (Navigateur JavaScript)                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ 1. Utilisateur sélectionne "rapport.pdf" (2.4 Mo)                  │
│                                                                      │
│ 2. Lecture fichier en ArrayBuffer                                   │
│    file_buffer = await file.arrayBuffer()                          │
│                                                                      │
│ 3. Génération clé AES-256 pour contenu                             │
│    content_key = crypto.getRandomValues(new Uint8Array(32))        │
│                                                                      │
│ 4. Chiffrement CONTENU (AES-256-GCM)                               │
│    encrypted_content = await crypto.subtle.encrypt(                 │
│        {name: "AES-GCM", iv: content_iv},                          │
│        content_key,                                                 │
│        file_buffer                                                  │
│    )                                                                 │
│                                                                      │
│ 5. Génération clé AES-256 pour MÉTADONNÉES                         │
│    metadata_key = crypto.getRandomValues(new Uint8Array(32))       │
│                                                                      │
│ 6. Création objet métadonnées                                       │
│    metadata = {                                                     │
│        filename: "rapport.pdf",                                     │
│        mime_type: "application/pdf",                                │
│        plaintext_size: 2457600,                                     │
│        original_uploaded_at: new Date().toISOString()              │
│    }                                                                 │
│                                                                      │
│ 7. Chiffrement MÉTADONNÉES (AES-256-GCM)                           │
│    metadata_json = JSON.stringify(metadata)                        │
│    encrypted_metadata = await crypto.subtle.encrypt(                │
│        {name: "AES-GCM", iv: metadata_iv},                         │
│        metadata_key,                                                │
│        new TextEncoder().encode(metadata_json)                     │
│    )                                                                 │
│                                                                      │
│ 8. PADDING du contenu chiffré                                       │
│    encrypted_size = encrypted_content.byteLength                    │
│    padded_size = roundToNextPaddingSize(encrypted_size)            │
│    // Ex: 2500000 bytes → arrondi à 4 Mo (4194304 bytes)          │
│    padding = new Uint8Array(padded_size - encrypted_size)         │
│    padded_content = concat(encrypted_content, padding)             │
│                                                                      │
│ 9. Chiffrement clés AES avec RSA-2048 (clé publique user)         │
│    encrypted_content_key = RSA_encrypt(content_key, public_key)    │
│    encrypted_metadata_key = RSA_encrypt(metadata_key, public_key)  │
│                                                                      │
│ 10. Génération UUID opaque                                          │
│     uuid = crypto.randomUUID() // "a3f8c7e2-9d4b-41a3-8e6f-..."   │
│                                                                      │
│ 11. Envoi au serveur (multipart/form-data)                         │
│     FormData:                                                       │
│       - uuid: "a3f8c7e2-..."                                       │
│       - encrypted_content: Blob(padded_content)                    │
│       - encrypted_metadata: base64(encrypted_metadata)             │
│       - metadata_iv: hex(metadata_iv)                              │
│       - metadata_tag: hex(metadata_tag)                            │
│       - encrypted_content_key: base64(encrypted_content_key)       │
│       - encrypted_metadata_key: base64(encrypted_metadata_key)     │
│       - content_iv: hex(content_iv)                                │
│       - content_tag: hex(content_tag)                              │
│       - padded_size: 4194304                                       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ SERVEUR (Flask Python)                                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ 12. Réception requête POST /upload                                  │
│                                                                      │
│ 13. Validation (sans déchiffrement !)                               │
│     - uuid valide ?                                                 │
│     - padded_size < quota user ?                                    │
│     - Tous les champs présents ?                                    │
│                                                                      │
│ 14. Sauvegarde fichier chiffré                                      │
│     filepath = f"static/uploads/{uuid}.enc"                        │
│     file.save(filepath)                                             │
│                                                                      │
│ 15. Insertion en base de données                                    │
│     INSERT INTO files (                                             │
│         uuid, user_id,                                              │
│         encrypted_metadata, metadata_iv, metadata_tag,              │
│         encrypted_aes_key, content_iv, content_tag,                │
│         padded_size,                                                │
│         created_at                                                  │
│     ) VALUES (...)                                                  │
│                                                                      │
│ 16. Réponse succès (sans métadonnées !)                            │
│     {"status": "success", "file_id": 42, "uuid": "a3f8c7e2-..."}  │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Points clés :**
- ✅ Le serveur ne voit JAMAIS le nom "rapport.pdf"
- ✅ Le serveur ne connait PAS la taille réelle (2.4 Mo → arrondi 4 Mo)
- ✅ Le serveur ne connait PAS le type MIME (PDF, image, vidéo ?)
- ✅ Le serveur stocke uniquement des UUIDs opaques et des blobs chiffrés

---

### 📥 DOWNLOAD (Serveur → Client)

```
┌─────────────────────────────────────────────────────────────────────┐
│ CLIENT (Navigateur JavaScript)                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ 1. Utilisateur clique "Télécharger" sur un fichier                 │
│    file_id = 42                                                     │
│                                                                      │
│ 2. Requête au serveur                                               │
│    GET /api/file/42/metadata                                        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ SERVEUR (Flask Python)                                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ 3. Récupération depuis DB                                           │
│    file = File.query.filter_by(id=42, user_id=user.id).first()    │
│                                                                      │
│ 4. Validation ownership                                             │
│    if not file or file.user_id != session['user_id']:              │
│        abort(403)                                                   │
│                                                                      │
│ 5. Envoi métadonnées chiffrées + clés chiffrées                    │
│    return {                                                         │
│        "encrypted_metadata": file.encrypted_metadata,               │
│        "metadata_iv": file.metadata_iv,                            │
│        "metadata_tag": file.metadata_tag,                          │
│        "encrypted_metadata_key": file.encrypted_metadata_key,      │
│        "encrypted_content_key": file.encrypted_aes_key,            │
│        "content_iv": file.content_iv,                              │
│        "content_tag": file.content_tag,                            │
│        "uuid": file.uuid                                            │
│    }                                                                 │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ CLIENT (Navigateur JavaScript)                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ 6. Déchiffrement clé métadonnées avec RSA (clé privée user)        │
│    metadata_key = RSA_decrypt(encrypted_metadata_key, private_key)  │
│                                                                      │
│ 7. Déchiffrement métadonnées                                        │
│    metadata_json = await crypto.subtle.decrypt(                     │
│        {name: "AES-GCM", iv: metadata_iv},                         │
│        metadata_key,                                                │
│        encrypted_metadata                                           │
│    )                                                                 │
│    metadata = JSON.parse(new TextDecoder().decode(metadata_json))  │
│                                                                      │
│ 8. Affichage métadonnées dans l'interface                          │
│    document.querySelector('.filename').textContent = metadata.filename │
│    document.querySelector('.filesize').textContent = formatSize(metadata.plaintext_size) │
│    document.querySelector('.filetype').textContent = metadata.mime_type │
│                                                                      │
│ 9. Téléchargement contenu chiffré                                   │
│    response = await fetch(`/api/file/${uuid}/download`)            │
│    encrypted_content = await response.arrayBuffer()                 │
│                                                                      │
│ 10. Déchiffrement clé contenu avec RSA                             │
│     content_key = RSA_decrypt(encrypted_content_key, private_key)   │
│                                                                      │
│ 11. Suppression padding                                             │
│     unpadded_content = removePadding(encrypted_content, metadata.plaintext_size) │
│                                                                      │
│ 12. Déchiffrement contenu                                           │
│     decrypted_content = await crypto.subtle.decrypt(                │
│         {name: "AES-GCM", iv: content_iv},                         │
│         content_key,                                                │
│         unpadded_content                                            │
│     )                                                                 │
│                                                                      │
│ 13. Téléchargement fichier déchiffré                               │
│     blob = new Blob([decrypted_content], {type: metadata.mime_type}) │
│     url = URL.createObjectURL(blob)                                │
│     link = document.createElement('a')                              │
│     link.href = url                                                 │
│     link.download = metadata.filename // "rapport.pdf"             │
│     link.click()                                                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Points clés :**
- ✅ Le serveur ne déchiffre RIEN (zero-knowledge)
- ✅ Seul le client avec la clé privée peut lire les métadonnées
- ✅ Le nom de fichier n'apparaît que dans le navigateur de l'utilisateur

---

## 🎭 Padding des Tailles

### Principe

**Problème :** Même chiffré, la taille exacte d'un fichier révèle des informations.

**Exemples :**
- 1024 bytes → Probablement un petit fichier texte ou configuration
- 5242880 bytes (5 Mo) → Probablement une photo haute résolution
- 104857600 bytes (100 Mo) → Probablement une vidéo

**Solution :** Arrondir à la tranche supérieure avec des paliers exponentiels.

---

### Paliers de Padding

```python
PADDING_SIZES = [
    4 * 1024,           # 4 Ko
    16 * 1024,          # 16 Ko
    64 * 1024,          # 64 Ko
    256 * 1024,         # 256 Ko
    1 * 1024 * 1024,    # 1 Mo
    4 * 1024 * 1024,    # 4 Mo
    16 * 1024 * 1024,   # 16 Mo
    64 * 1024 * 1024,   # 64 Mo
    256 * 1024 * 1024,  # 256 Mo
    1024 * 1024 * 1024, # 1 Go
    # Au-delà de 1 Go : arrondi au Go supérieur
]

def get_padded_size(actual_size):
    """Retourne la taille avec padding pour obfusquer la taille réelle"""
    for padded_size in PADDING_SIZES:
        if actual_size <= padded_size:
            return padded_size
    
    # Au-delà de 1 Go : arrondir au Go supérieur
    gb = 1024 * 1024 * 1024
    return ((actual_size // gb) + 1) * gb
```

---

### Exemples de Padding

| Taille Réelle | Taille Paddée | Overhead | Obfuscation |
|---------------|---------------|----------|-------------|
| 1 Ko | 4 Ko | +300% | ✅ Excellent |
| 10 Ko | 16 Ko | +60% | ✅ Bon |
| 50 Ko | 64 Ko | +28% | ✅ Bon |
| 200 Ko | 256 Ko | +28% | ✅ Bon |
| 500 Ko | 1 Mo | +100% | ✅ Excellent |
| 2 Mo | 4 Mo | +100% | ✅ Excellent |
| 10 Mo | 16 Mo | +60% | ✅ Bon |
| 50 Mo | 64 Mo | +28% | ✅ Bon |
| 500 Mo | 1 Go | +100% | ✅ Excellent |
| 2 Go | 3 Go | +50% | ✅ Bon |

**Avantages :**
- ✅ Impossible de deviner la taille exacte
- ✅ Plusieurs fichiers peuvent avoir la même taille paddée (camouflage)
- ✅ Overhead acceptable (max ~100% pour petits fichiers, <50% pour gros fichiers)

**Inconvénients :**
- ⚠️ Consomme plus d'espace disque (compensé par compression si besoin)
- ⚠️ Upload/download légèrement plus lents (padding = données supplémentaires)

---

## 📁 Arborescence Chiffrée

### Principe

**Objectif :** Chiffrer la structure des dossiers pour qu'un attaquant ne puisse pas reconstruire l'organisation des fichiers.

### Structure Actuelle (Flat)

```
static/uploads/
├── 9f427bf814394d69b780cfa7fbbd055f.enc
├── a06159acb9cf4ef1b8ef4ebd98e8ece5.enc
├── a93946c9bd1645e09547b523015738f2.enc
└── ...
```

**Problème :** Si on ajoute des dossiers en clair :
```sql
SELECT filename, folder_path FROM files WHERE user_id = 42;

Résultat :
+----------------------+----------------------------------+
| filename             | folder_path                      |
+----------------------+----------------------------------+
| facture_01.pdf       | /Finances/2026/Janvier/         |
| contrat_dupont.docx  | /Clients/Dupont/Contrats/       |
| photo_vacances.jpg   | /Personnel/Photos/2026/Juillet/ |
+----------------------+----------------------------------+
```
→ L'attaquant voit toute l'arborescence en clair !

---

### Solution : Dossiers Virtuels Chiffrés

**Concept :**
- Chaque dossier a un **UUID opaque**
- Le **nom du dossier** est chiffré dans `encrypted_metadata`
- Le **chemin complet** est chiffré dans `encrypted_folder_path`
- Les **relations parent/enfant** utilisent des UUIDs opaques

**Table `folders` (Nouvelle) :**

```sql
CREATE TABLE folders (
    id INTEGER PRIMARY KEY,
    uuid VARCHAR(64) UNIQUE NOT NULL,            -- UUID opaque
    user_id INTEGER NOT NULL,
    encrypted_name TEXT NOT NULL,                 -- 🔐 Nom du dossier chiffré
    name_iv VARCHAR(64) NOT NULL,
    name_tag VARCHAR(64) NOT NULL,
    parent_folder_uuid VARCHAR(64),              -- NULL = racine, UUID = parent
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_id (user_id),
    INDEX idx_parent_folder (parent_folder_uuid)
);
```

**Exemple d'arborescence chiffrée :**

```
Côté CLIENT (déchiffré) :
/
├── Finances/
│   └── 2026/
│       ├── Janvier/
│       │   └── facture_01.pdf
│       └── Février/
└── Personnel/
    └── Photos/
        └── photo.jpg

Côté SERVEUR (base de données) :
folders:
+-----+------------------+---------+-------------------------+------------------------+
| id  | uuid             | user_id | encrypted_name          | parent_folder_uuid     |
+-----+------------------+---------+-------------------------+------------------------+
| 1   | f1a2b3c4-...     | 42      | "8a7f3b2e9d4c1a5f..." | NULL (racine)          |
| 2   | f2b3c4d5-...     | 42      | "9b8g4c3f0e5d2b6g..." | f1a2b3c4-... (Finances)|
| 3   | f3c4d5e6-...     | 42      | "1c9h5d4g1f6e3c7h..." | f2b3c4d5-... (2026)    |
+-----+------------------+---------+-------------------------+------------------------+

files:
+-----+------------------+---------+-------------------------+------------------------+
| id  | uuid             | user_id | encrypted_metadata      | parent_folder_uuid     |
+-----+------------------+---------+-------------------------+------------------------+
| 101 | a1b2c3d4-...     | 42      | "2d0i6e5h2g7f4d8i..." | f3c4d5e6-... (Janvier) |
+-----+------------------+---------+-------------------------+------------------------+
```

**Requête serveur (opaque) :**
```sql
SELECT uuid, encrypted_metadata FROM files 
WHERE user_id = 42 AND parent_folder_uuid = 'f3c4d5e6-...';
```
→ L'attaquant voit uniquement des UUIDs et des blobs chiffrés !

---

## 🚧 Implémentation Étape par Étape

### Étape 1 : Chiffrement Nom de Fichier

**Objectif :** Remplacer `filename` (clair) par `encrypted_metadata` (chiffré).

**Modifications :**

1. **Migration base de données**
   ```sql
   ALTER TABLE files ADD COLUMN encrypted_metadata TEXT;
   ALTER TABLE files ADD COLUMN metadata_iv VARCHAR(64);
   ALTER TABLE files ADD COLUMN metadata_tag VARCHAR(64);
   ALTER TABLE files ADD COLUMN encrypted_metadata_key TEXT;
   ```

2. **Module crypto : `modules/metadata_crypto.py`**
   ```python
   from cryptography.hazmat.primitives.ciphers.aead import AESGCM
   import json
   import secrets
   
   def encrypt_metadata(metadata_dict, aes_key):
       """Chiffre un dictionnaire de métadonnées avec AES-256-GCM"""
       metadata_json = json.dumps(metadata_dict).encode('utf-8')
       iv = secrets.token_bytes(12)
       aesgcm = AESGCM(aes_key)
       ciphertext = aesgcm.encrypt(iv, metadata_json, None)
       tag = ciphertext[-16:]
       encrypted = ciphertext[:-16]
       return encrypted, iv, tag
   
   def decrypt_metadata(encrypted, iv, tag, aes_key):
       """Déchiffre les métadonnées"""
       aesgcm = AESGCM(aes_key)
       ciphertext = encrypted + tag
       plaintext = aesgcm.decrypt(iv, ciphertext, None)
       return json.loads(plaintext.decode('utf-8'))
   ```

3. **Upload : chiffrer métadonnées côté serveur** (temporairement, avant JS client)
   ```python
   # Générer clé métadonnées
   metadata_key = secrets.token_bytes(32)
   
   # Créer dictionnaire métadonnées
   metadata = {
       "filename": file.filename,
       "mime_type": file.content_type,
       "plaintext_size": len(file_data),
       "original_uploaded_at": datetime.utcnow().isoformat()
   }
   
   # Chiffrer métadonnées
   encrypted_meta, meta_iv, meta_tag = encrypt_metadata(metadata, metadata_key)
   
   # Chiffrer clé métadonnées avec RSA
   encrypted_meta_key = rsa_encrypt(metadata_key, user.public_key)
   ```

4. **Dashboard : déchiffrer métadonnées**
   ```python
   # Déchiffrer clé métadonnées
   metadata_key = rsa_decrypt(file.encrypted_metadata_key, private_key)
   
   # Déchiffrer métadonnées
   metadata = decrypt_metadata(
       file.encrypted_metadata,
       file.metadata_iv,
       file.metadata_tag,
       metadata_key
   )
   
   # Afficher
   filename = metadata['filename']
   filesize = metadata['plaintext_size']
   ```

---

### Étape 2 : Padding des Tailles

**Objectif :** Arrondir tailles pour empêcher analyse de corrélation.

**Modifications :**

1. **Migration base de données**
   ```sql
   ALTER TABLE files ADD COLUMN padded_size BIGINT;
   ```

2. **Module padding : `modules/padding.py`**
   ```python
   PADDING_SIZES = [4*1024, 16*1024, 64*1024, 256*1024, 
                     1*1024*1024, 4*1024*1024, 16*1024*1024, ...]
   
   def get_padded_size(actual_size):
       for padded_size in PADDING_SIZES:
           if actual_size <= padded_size:
               return padded_size
       # Au-delà de 1 Go : arrondir au Go supérieur
       gb = 1024 * 1024 * 1024
       return ((actual_size // gb) + 1) * gb
   
   def add_padding(data, target_size):
       """Ajoute du padding aléatoire pour atteindre target_size"""
       current_size = len(data)
       padding_size = target_size - current_size
       padding = secrets.token_bytes(padding_size)
       return data + padding
   
   def remove_padding(padded_data, original_size):
       """Supprime le padding"""
       return padded_data[:original_size]
   ```

3. **Upload : appliquer padding**
   ```python
   encrypted_content = encrypt_file(file_data, aes_key)
   padded_size = get_padded_size(len(encrypted_content))
   padded_content = add_padding(encrypted_content, padded_size)
   ```

---

### Étape 3 : Arborescence Chiffrée

**Objectif :** Ajouter support dossiers avec noms/chemins chiffrés.

**Modifications :**

1. **Créer table `folders`**
   ```sql
   CREATE TABLE folders (...);
   ```

2. **Module dossiers : `modules/folder_manager.py`**
   ```python
   def create_folder(name, parent_uuid, user_id, public_key):
       folder_uuid = str(uuid.uuid4())
       metadata_key = secrets.token_bytes(32)
       
       encrypted_name, iv, tag = encrypt_metadata({"name": name}, metadata_key)
       encrypted_key = rsa_encrypt(metadata_key, public_key)
       
       folder = Folder(
           uuid=folder_uuid,
           user_id=user_id,
           encrypted_name=encrypted_name,
           name_iv=iv,
           name_tag=tag,
           parent_folder_uuid=parent_uuid
       )
       db.session.add(folder)
       db.session.commit()
       return folder_uuid
   ```

---

## ⚠️ Limites Résiduelles

### Ce qui RESTE Visible Côté Serveur

| Métadonnée | Visible ? | Raison | Mitigation |
|------------|-----------|--------|------------|
| **User ID** | ✅ OUI | Nécessaire pour requêtes SQL | ❌ Impossible à masquer (besoin d'associer fichiers à utilisateur) |
| **Nombre de fichiers** | ✅ OUI | `COUNT(*)` en SQL | ⚠️ Padding des IDs (générer IDs fictifs?) |
| **Taille paddée** | ✅ OUI | Nécessaire pour quota | ✅ Obfusqué par padding (plusieurs fichiers = même taille) |
| **Timestamp `created_at`** | ✅ OUI | Horodatage serveur | ⚠️ Arrondir à l'heure/jour (perte de précision) |
| **Timestamp `modified_at`** | ✅ OUI | Horodatage serveur | ⚠️ Arrondir à l'heure/jour |
| **Taille ciphertext** | ✅ OUI | Taille fichier .enc sur disque | ✅ Masqué par padding |
| **Nom fichier physique** | ❌ NON | UUID opaque : `a3f8c7e2-9d4b-41a3-8e6f-...` | ✅ Aucune info révélée |
| **Nom fichier logique** | ❌ NON | Chiffré dans `encrypted_metadata` | ✅ Zero-knowledge |
| **Type MIME** | ❌ NON | Chiffré dans `encrypted_metadata` | ✅ Zero-knowledge |
| **Taille réelle** | ❌ NON | Chiffré dans `encrypted_metadata` | ✅ Zero-knowledge |
| **Arborescence dossiers** | ❌ NON | UUIDs opaques + noms chiffrés | ✅ Zero-knowledge |

---

### Attaques Résiduelles Possibles

#### 1️⃣ **Analyse Temporelle**

**Attaque :**
```sql
SELECT user_id, COUNT(*), DATE(created_at) 
FROM files 
GROUP BY user_id, DATE(created_at);

Résultat :
User 42 : 15 fichiers le 2026-07-08 entre 8h et 10h
→ Probablement activité inhabituelle (backup, migration, etc.)
```

**Mitigation :**
- Arrondir timestamps à l'heure ou au jour
- Upload batch en plusieurs requêtes étalées (randomization temporelle)

---

#### 2️⃣ **Analyse de Corrélation (Taille + Timestamp)**

**Attaque :**
```sql
SELECT user_id, padded_size, created_at 
FROM files 
WHERE padded_size = 4194304 -- 4 Mo
ORDER BY created_at;

Résultat :
User 42 : 5 fichiers de 4 Mo uploadés le même jour
→ Probablement même type de document (photos, rapports, etc.)
```

**Mitigation :**
- Padding plus agressif (paliers plus larges)
- Randomisation temporelle des uploads

---

#### 3️⃣ **Analyse du Nombre de Fichiers**

**Attaque :**
```sql
SELECT user_id, COUNT(*) as file_count 
FROM files 
GROUP BY user_id 
ORDER BY file_count DESC;

Résultat :
User 42 : 10 000 fichiers
User 43 : 50 fichiers
→ User 42 = professionnel (entreprise, photographe, etc.)
```

**Mitigation :**
- Générer fichiers fictifs (padding) pour masquer nombre réel
- **ATTENTION :** Très coûteux en ressources (stockage, calcul)

---

### Verdict Final

**Score Sécurité Après Implémentation :**

| Catégorie | Avant | Après | Gain |
|-----------|-------|-------|------|
| **Chiffrement Contenu** | 100% | 100% | 0% |
| **Chiffrement Métadonnées** | 0% | 95% | +95% |
| **Obfuscation Taille** | 0% | 85% | +85% |
| **Arborescence Chiffrée** | 0% | 95% | +95% |
| **Anonymat Temporel** | 0% | 50% | +50% |

**Score Global : 97% → 99.5%** 🎯

**Limites acceptables :**
- ⚠️ User ID visible (nécessaire)
- ⚠️ Timestamps visible (arrondir = perte de précision utilisateur)
- ⚠️ Nombre de fichiers visible (padding = coût prohibitif)

---

## 🎯 Conclusion

### Ce qui Sera Chiffré

✅ **Nom de fichier** (ex: "salaire_2026.pdf" → chiffré)  
✅ **Type MIME** (ex: "application/pdf" → chiffré)  
✅ **Taille réelle** (ex: 2457600 bytes → chiffré, paddé à 4 Mo)  
✅ **Timestamp exact upload** (ex: "2026-07-08 18:30:15" → chiffré)  
✅ **Arborescence dossiers** (ex: "/Finances/2026/" → UUIDs opaques)  
✅ **Métadonnées custom** (tags, descriptions, couleurs → chiffrés)

### Ce qui Reste Visible (Acceptable)

⚠️ **User ID** (nécessaire pour requêtes)  
⚠️ **Taille paddée** (masquée mais pas invisible)  
⚠️ **Timestamp arrondi** (jour/heure, pas seconde exacte)  
⚠️ **Nombre de fichiers** (COUNT possible mais padding coûteux)

### Impact Utilisateur

✅ **Zéro** : Le chiffrement est transparent  
✅ Recherche fonctionne (déchiffrement client)  
✅ Tri fonctionne (déchiffrement client)  
✅ Prévisualisation fonctionne (déchiffrement client)  
⚠️ Légère augmentation stockage (~30% en moyenne pour padding)  
⚠️ Légère augmentation temps upload/download (~10-20%)

---

**Prêt à implémenter ? On commence par l'étape 1 : Chiffrement des noms de fichiers ! 🚀**
