#!/usr/bin/env python3
"""Vérifier les dates des utilisateurs"""

from app import app, db
from database.models import User
from datetime import datetime, timezone

with app.app_context():
    users = User.query.filter_by(is_admin=False).limit(5).all()
    
    print("📅 Vérification dates utilisateurs\n")
    
    for u in users:
        print(f"• {u.email}")
        print(f"  created_at type: {type(u.created_at)}")
        print(f"  created_at value: {u.created_at}")
        
        if u.created_at:
            # Vérifier si timezone-aware
            if u.created_at.tzinfo:
                print(f"  ✅ Timezone-aware")
            else:
                print(f"  ⚠️  Timezone-naive (OK pour comparaison)")
        print()
