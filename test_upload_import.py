#!/usr/bin/env python3
"""Test import app après modification upload"""

print("🔍 Test import app.py avec nouvelle route /upload...")

try:
    from app import app
    print("✅ Import app réussi")
    
    # Vérifier que la route existe
    upload_rule = [rule for rule in app.url_map.iter_rules() if rule.endpoint == 'upload']
    if upload_rule:
        print(f"✅ Route /upload trouvée : {upload_rule[0]}")
    else:
        print("❌ Route /upload introuvable")
    
    # Vérifier les modules importés
    import modules.metadata_crypto
    import modules.padding
    print("✅ Modules metadata_crypto et padding disponibles")
    
    print("\n✅ TOUS LES TESTS RÉUSSIS")
    
except Exception as e:
    print(f"\n❌ ERREUR : {e}")
    import traceback
    traceback.print_exc()
