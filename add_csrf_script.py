#!/usr/bin/env python3
"""
Script pour ajouter le script CSRF avant </body> dans tous les templates
"""
import os
import re

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')

def add_csrf_script_before_body(content):
    """Ajoute le script CSRF avant la fermeture de </body>"""
    # Si déjà présent, ne rien faire
    if "csrf_script.html" in content or "/static/js/csrf.js" in content:
        return content, False
    
    # Chercher </body> et ajouter avant
    pattern = r'(</body>)'
    replacement = r"{% include 'partials/csrf_script.html' %}\n\1"
    
    new_content, count = re.subn(pattern, replacement, content, count=1)
    return new_content, count > 0

def process_template(filepath):
    """Traite un template HTML"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    content, modified = add_csrf_script_before_body(content)
    
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    
    return False

def main():
    """Parcourt tous les templates et ajoute le script CSRF"""
    print("🔒 Ajout du script CSRF dans les templates...\n")
    
    total_files = 0
    modified_files = 0
    
    for root, dirs, files in os.walk(TEMPLATES_DIR):
        # Ignorer le dossier partials
        if 'partials' in root:
            continue
        
        for filename in files:
            if filename.endswith('.html'):
                filepath = os.path.join(root, filename)
                relative_path = os.path.relpath(filepath, TEMPLATES_DIR)
                total_files += 1
                
                try:
                    modified = process_template(filepath)
                    
                    if modified:
                        modified_files += 1
                        print(f"✅ {relative_path}")
                    else:
                        print(f"⏭️  {relative_path} - Déjà inclus")
                
                except Exception as e:
                    print(f"❌ {relative_path} - Erreur: {e}")
    
    print(f"\n{'='*60}")
    print(f"📊 RÉSUMÉ")
    print(f"{'='*60}")
    print(f"Total de fichiers scannés : {total_files}")
    print(f"Fichiers modifiés         : {modified_files}")
    print(f"\n✅ Script CSRF ajouté avec succès !")

if __name__ == '__main__':
    main()
