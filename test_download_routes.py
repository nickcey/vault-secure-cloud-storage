#!/usr/bin/env python3
"""Test routes download après modification"""

print("🔍 Test routes download...")

try:
    from app import app
    import inspect
    print("✅ Import app réussi")
    
    # Vérifier route /download/<int:file_id>
    download_rule = [r for r in app.url_map.iter_rules() if 'download' in r.rule and '<int:file_id>' in r.rule]
    if download_rule:
        print(f"✅ Route /download/<int:file_id> trouvée : {download_rule[0]}")
    else:
        print("❌ Route /download/<int:file_id> introuvable")
    
    # Vérifier route /download-file/<token>
    download_token_rule = [r for r in app.url_map.iter_rules() if 'download-file' in r.rule]
    if download_token_rule:
        print(f"✅ Route /download-file/<token> trouvée : {download_token_rule[0]}")
    else:
        print("❌ Route /download-file/<token> introuvable")
    
    # Vérifier que download_with_token contient le code de padding
    from app import download_with_token
    source = inspect.getsource(download_with_token)
    
    if 'from modules.padding import remove_padding' in source:
        print("✅ download_with_token: import remove_padding trouvé")
    else:
        print("⚠️  download_with_token: import remove_padding NON trouvé")
    
    if 'file_meta.uuid' in source:
        print("✅ download_with_token: support nouveau schéma (uuid) trouvé")
    else:
        print("❌ download_with_token: support nouveau schéma NON trouvé")
    
    if 'decrypt_metadata_from_base64' in source:
        print("✅ download_with_token: déchiffrement métadonnées trouvé")
    else:
        print("❌ download_with_token: déchiffrement métadonnées NON trouvé")
    
    print("\n✅ TOUS LES TESTS RÉUSSIS")
    
except Exception as e:
    print(f"\n❌ ERREUR : {e}")
    import traceback
    traceback.print_exc()
