#!/usr/bin/env python3
"""
Script pour ajouter automatiquement les tokens CSRF dans tous les templates
"""
import os
import re

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'templates')

def add_meta_csrf_to_head(content):
    """Ajoute la meta tag CSRF dans le <head>"""
    # Si déjà présent, ne rien faire
    if 'name="csrf-token"' in content:
        return content, False
    
    # Chercher <head> et ajouter après
    pattern = r'(<head>[\s\S]*?<meta charset="UTF-8">[\s\S]*?<meta name="viewport"[^>]+>)'
    replacement = r'\1\n<meta name="csrf-token" content="{{ csrf_token() }}">'
    
    new_content, count = re.subn(pattern, replacement, content, count=1)
    return new_content, count > 0

def add_csrf_token_to_form(content):
    """Ajoute le token CSRF après chaque balise <form method="POST">"""
    # Pattern pour détecter les formulaires POST
    pattern = r'(<form[^>]+method\s*=\s*["\']POST["\'][^>]*>)(\s*)'
    
    def replace_form(match):
        form_tag = match.group(1)
        whitespace = match.group(2)
        
        # Si le token CSRF est déjà présent, ne rien faire
        if "{% include 'partials/csrf_token.html' %}" in content[match.start():match.start()+500]:
            return match.group(0)
        if 'csrf_token()' in content[match.start():match.start()+500]:
            return match.group(0)
        
        return f"{form_tag}{whitespace}      {{% include 'partials/csrf_token.html' %}}\n"
    
    new_content = re.sub(pattern, replace_form, content, flags=re.IGNORECASE)
    return new_content, new_content != content

def process_template(filepath):
    """Traite un template HTML"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    modified = False
    
    # Ajouter la meta tag CSRF
    content, meta_added = add_meta_csrf_to_head(content)
    modified = modified or meta_added
    
    # Ajouter les tokens CSRF aux formulaires
    content, forms_added = add_csrf_token_to_form(content)
    modified = modified or forms_added
    
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True, meta_added, forms_added
    
    return False, False, False

def main():
    """Parcourt tous les templates et ajoute les tokens CSRF"""
    print("🔒 Ajout des tokens CSRF dans les templates...\n")
    
    total_files = 0
    modified_files = 0
    meta_added_count = 0
    forms_added_count = 0
    
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
                    modified, meta_added, forms_added = process_template(filepath)
                    
                    if modified:
                        modified_files += 1
                        status = []
                        if meta_added:
                            status.append("meta CSRF")
                            meta_added_count += 1
                        if forms_added:
                            status.append("tokens formulaires")
                            forms_added_count += 1
                        
                        print(f"✅ {relative_path} - Ajouté: {', '.join(status)}")
                    else:
                        print(f"⏭️  {relative_path} - Déjà protégé")
                
                except Exception as e:
                    print(f"❌ {relative_path} - Erreur: {e}")
    
    print(f"\n{'='*60}")
    print(f"📊 RÉSUMÉ")
    print(f"{'='*60}")
    print(f"Total de fichiers scannés : {total_files}")
    print(f"Fichiers modifiés         : {modified_files}")
    print(f"Meta tags ajoutées        : {meta_added_count}")
    print(f"Formulaires protégés      : {forms_added_count}")
    print(f"\n✅ Protection CSRF implémentée avec succès !")

if __name__ == '__main__':
    main()
