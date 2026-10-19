# Système d'Icônes SVG Dynamiques - Vault

## Vue d'ensemble

Ce système génère des icônes SVG personnalisées pour chaque type de fichier, avec des couleurs spécifiques à chaque catégorie dans le thème cyberpunk de Vault.

## Architecture

### 1. Fichier principal : `file_icons.py`

```python
from utils.file_icons import get_file_icon_data, get_file_category
```

### 2. Fonctions principales

#### `get_file_icon_data(ext)`

Retourne toutes les données nécessaires pour afficher l'icône d'un fichier.

**Paramètres :**
- `ext` (str) : Extension du fichier sans le point (ex: 'pdf', 'jpg')

**Retour :**
```python
{
    'path': str,        # Chemin SVG
    'viewbox': str,     # viewBox SVG
    'color': str,       # Couleur de l'icône (hex)
    'glow': str,        # Couleur du glow (rgba)
    'bg_color': str,    # Couleur de fond (rgba)
    'category': str     # Catégorie du fichier
}
```

#### `get_file_category(ext)`

Retourne la catégorie d'un fichier basée sur son extension.

**Catégories disponibles :**
- `document` : PDF, DOC, DOCX, TXT, CSV, etc.
- `image` : JPG, PNG, GIF, WEBP, etc.
- `archive` : ZIP, RAR, 7Z, TAR, GZ
- `audio` : MP3, WAV, OGG, FLAC, etc.
- `video` : MP4, AVI, MKV, MOV, etc.
- `code` : PY, JAVA, C, CPP, JSON, etc.
- `default` : Fichiers non reconnus

## Couleurs par Catégorie

| Catégorie | Couleur principale | Exemple |
|-----------|-------------------|---------|
| Documents | `#4a9eff` (Bleu cyber) | DOC, DOCX |
| PDF       | `#ff3b44` (Rouge ember) | PDF |
| Images    | `#a855f7` (Violet néon) | JPG, PNG |
| GIF       | `#d946ef` (Magenta) | GIF |
| Archives  | `#f59e0b` (Orange) | ZIP, RAR |
| Audio     | `#ec4899` (Rose) | MP3, WAV |
| Vidéo     | `#ef4444` (Rouge vif) | MP4, AVI |
| Code      | `#94a3b8` (Gris tech) | JSON, XML |
| Python    | `#facc15` (Jaune) | PY |
| Java      | `#f97316` (Orange) | JAVA |
| C/C++     | `#60a5fa` (Bleu clair) | C, CPP |
| Ruby      | `#ef4444` (Rouge rubis) | RB |
| Rust      | `#fb923c` (Orange) | RS |
| Go        | `#06b6d4` (Cyan) | GO |

## Utilisation dans Flask

### 1. Dans la route Python

```python
from utils.file_icons import get_file_icon_data

@app.route('/dashboard')
def dashboard():
    files = FileMetadata.query.filter_by(user_id=user.id).all()
    files_data = []
    
    for f in files:
        # Extraire l'extension
        ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
        
        # Obtenir les données de l'icône
        icon_data = get_file_icon_data(ext)
        
        files_data.append({
            'id': f.id,
            'name': f.filename,
            'ext': ext,
            'icon': icon_data  # ← Ajouter les données d'icône
        })
    
    return render_template('dashboard.html', files=files_data)
```

### 2. Dans le template Jinja2

```html
{% for file in files %}
  <div class="file-icon" 
       style="--icon-color: {{ file.icon.color }}; 
              --icon-glow: {{ file.icon.glow }}; 
              --icon-bg: {{ file.icon.bg_color }};">
    <svg viewBox="{{ file.icon.viewbox }}" 
         fill="none" 
         stroke="currentColor" 
         stroke-width="1.8" 
         stroke-linecap="round" 
         stroke-linejoin="round" 
         width="20" height="20">
      <path d="{{ file.icon.path }}"/>
    </svg>
  </div>
{% endfor %}
```

### 3. CSS requis

```css
.file-icon{
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--icon-bg, rgba(200,30,44,0.10));
  border: 1px solid rgba(200,30,44,0.2);
  color: var(--icon-color, #ff3b44);
  transition: all 0.3s ease;
}

.file-icon svg{
  filter: drop-shadow(0 0 3px var(--icon-glow, rgba(255,59,68,0.3)));
  transition: filter 0.3s ease;
}

/* Effet hover */
tr:hover .file-icon{
  box-shadow: 0 0 12px rgba(200,30,44,0.2);
  transform: scale(1.08);
}

tr:hover .file-icon svg{
  filter: drop-shadow(0 0 6px var(--icon-glow, rgba(255,59,68,0.6)));
}
```

## Extensions Supportées

**Total : 60+ extensions**

### Documents (12)
pdf, doc, docx, txt, md, csv, xls, xlsx, ppt, pptx, odt, rtf

### Images (9)
jpg, jpeg, png, gif, webp, bmp, ico, tiff, tif

### Archives (5)
zip, rar, 7z, tar, gz

### Audio (7)
mp3, wav, ogg, flac, m4a, aac, wma

### Vidéo (9)
mp4, avi, mkv, mov, wmv, flv, webm, mpeg, mpg

### Code (17)
py, java, c, cpp, h, cs, go, rs, swift, kt, rb, pl, json, xml, yaml, yml, toml, ini

## Ajouter une Nouvelle Extension

Pour ajouter une nouvelle extension :

1. Ouvrir `utils/file_icons.py`
2. Ajouter l'entrée dans `FILE_ICONS_SVG` :

```python
'mon_extension': {
    'path': 'M... (SVG path)',
    'viewbox': '0 0 24 24',
    'color': '#FF0000',  # Couleur principale
    'glow': 'rgba(255,0,0,0.5)'  # Couleur du glow
}
```

3. Ajouter l'extension dans la catégorie appropriée de `get_file_category()` :

```python
categories = {
    'document': ['pdf', ..., 'mon_extension'],
    ...
}
```

## Icônes par Défaut

Si une extension n'est pas reconnue, une icône générique de document est affichée avec la couleur `#f3e6e4` (bone).

## Performance

- **Poids** : ~5-10 KB pour toutes les icônes (SVG inline)
- **Aucune dépendance externe** : Pas de CDN, pas de requêtes HTTP
- **Zero latence** : Icônes générées côté serveur
- **Scalabilité parfaite** : SVG = vectoriel

## Compatibilité

- ✅ Tous les navigateurs modernes (Chrome, Firefox, Safari, Edge)
- ✅ Mode clair / sombre automatique via variables CSS
- ✅ Responsive (mobile & desktop)
- ✅ Accessibilité (aria-labels possibles sur les SVG)

## Avantages vs Alternatives

| Solution | Poids | Dépendances | Cohérence | Couleurs |
|----------|-------|-------------|-----------|----------|
| **SVG Custom** | ⭐⭐⭐⭐⭐ | ✅ Aucune | ⭐⭐⭐⭐⭐ | ✅ Full control |
| Emojis | ⭐⭐⭐⭐⭐ | ✅ Aucune | ⭐ | ❌ OS-dépendant |
| Font Awesome | ⭐⭐ | ❌ CDN | ⭐⭐⭐⭐ | ⚠️ Limité |
| Material Icons | ⭐⭐⭐ | ❌ Google | ⭐⭐⭐ | ❌ Non |

## Exemples Visuels

```
PDF    → 📕 Rouge ember (#ff3b44)
JPG    → 🖼️  Violet néon (#a855f7)
MP3    → 🎵 Rose magenta (#ec4899)
MP4    → 🎬 Rouge vif (#ef4444)
ZIP    → 📦 Orange (#f59e0b)
PY     → 🐍 Jaune (#facc15)
JSON   → 📋 Gris tech (#94a3b8)
```

## Maintenance

- Les paths SVG sont tirés de [Feather Icons](https://feathericons.com/) et [Heroicons](https://heroicons.com/)
- License : MIT (usage libre)
- Dernière mise à jour : 2026-09-09

---

**Développé pour Vault Cloud Storage**  
Système d'icônes SVG dynamiques v1.0
