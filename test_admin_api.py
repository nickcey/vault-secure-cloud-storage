#!/usr/bin/env python3
"""Test API admin stats"""

from app import app
import json

print("🔍 Test API /admin/api/stats\n")

with app.test_client() as client:
    with app.app_context():
        # Simuler connexion admin
        from database.models import User
        admin = User.query.filter_by(is_admin=True).first()
        
        if not admin:
            print("❌ Aucun admin trouvé en DB")
            print("   Créez un compte admin d'abord")
            exit(1)
        
        print(f"✅ Admin trouvé : {admin.email}\n")
        
        # Appeler l'API directement (sans session)
        from app import admin_api_stats
        from flask import session
        
        # Simuler session admin
        with client.session_transaction() as sess:
            sess['user_id'] = admin.id
            sess['is_admin'] = True
        
        # Appeler route
        response = client.get('/admin/api/stats')
        
        print(f"📊 Status : {response.status_code}")
        
        if response.status_code == 200:
            data = response.get_json()
            print(f"✅ API fonctionne !\n")
            print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            print(f"❌ Erreur API")
            print(response.data.decode('utf-8'))
