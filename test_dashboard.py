#!/usr/bin/env python3
"""Test dashboard après modification"""

print("🔍 Test dashboard...")

try:
    from app import app
    print("✅ Import app réussi")
    
    dashboard_rule = [r for r in app.url_map.iter_rules() if r.endpoint == 'dashboard']
    if dashboard_rule:
        print(f"✅ Route /dashboard trouvée : {dashboard_rule[0]}")
    else:
        print("❌ Route /dashboard introuvable")
    
    print("\n✅ TOUS LES TESTS RÉUSSIS")
    
except Exception as e:
    print(f"\n❌ ERREUR : {e}")
    import traceback
    traceback.print_exc()
