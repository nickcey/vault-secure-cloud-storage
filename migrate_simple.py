#!/usr/bin/env python3
"""
Migration simplifiée SQLite -> PostgreSQL
"""
import os
import sys

# Forcer SQLite d'abord pour créer l'app
os.environ.pop('DATABASE_URL', None)

from app import app, db
from database.models import User, FileMetadata, ActivityLog, ActiveSession, Payment, DownloadToken, PromoCode, SharedLink
import json

print("=" * 70)
print("🔄 EXPORT DES DONNÉES SQLITE")
print("=" * 70)

# Exporter toutes les données en JSON
data_export = {
    'users': [],
    'files': [],
    'activity': [],
    'sessions': [],
    'payments': [],
    'tokens': [],
    'promos': [],
    'links': []
}

with app.app_context():
    print("\n📦 Lecture de SQLite...")
    
    # Users
    users = User.query.all()
    for u in users:
        user_data = {
            'id': u.id,
            'email': u.email,
            'username': getattr(u, 'username', u.email.split('@')[0]),
            'password_hash': u.password_hash,
            'salt': u.salt,
            'encrypted_private_key': u.encrypted_private_key,
            'recovery_hint': getattr(u, 'recovery_hint', None),
            'plan': getattr(u, 'plan', 'free'),
            'storage_used': getattr(u, 'storage_used', 0),
            'subscription_expiry': u.subscription_expiry.isoformat() if hasattr(u, 'subscription_expiry') and u.subscription_expiry else None,
            'otp_secret': getattr(u, 'otp_secret', None),
            'otp_expiry': getattr(u, 'otp_expiry', 0),
            'is_temp_password': getattr(u, 'is_temp_password', False),
            'is_admin': getattr(u, 'is_admin', False),
            'is_suspended': getattr(u, 'is_suspended', False),
            'language': getattr(u, 'language', 'fr'),
            'created_at': u.created_at.isoformat() if hasattr(u, 'created_at') and u.created_at else None
        }
        data_export['users'].append(user_data)
    print(f"   ✅ {len(users)} utilisateurs exportés")
    
    # Files
    files = FileMetadata.query.all()
    for f in files:
        file_data = {
            'id': f.id,
            'user_id': f.user_id,
            'original_filename': getattr(f, 'original_filename', getattr(f, 'filename', 'unknown')),
            'encrypted_filename': getattr(f, 'encrypted_filename', f.id),
            'file_size': getattr(f, 'file_size', 0),
            'encrypted_key': getattr(f, 'encrypted_key', ''),
            'upload_date': f.upload_date.isoformat() if hasattr(f, 'upload_date') and f.upload_date else None,
            'is_deleted': getattr(f, 'is_deleted', False),
            'deleted_at': f.deleted_at.isoformat() if hasattr(f, 'deleted_at') and f.deleted_at else None
        }
        data_export['files'].append(file_data)
    print(f"   ✅ {len(files)} fichiers exportés")
    
    # Activity logs
    logs = ActivityLog.query.all()
    for log in logs:
        log_data = {
            'id': log.id,
            'user_id': log.user_id,
            'action': getattr(log, 'action', ''),
            'timestamp': log.timestamp.isoformat() if hasattr(log, 'timestamp') and log.timestamp else None,
            'ip_address': getattr(log, 'ip_address', None)
        }
        data_export['activity'].append(log_data)
    print(f"   ✅ {len(logs)} logs exportés")
    
    # Sessions
    sessions = ActiveSession.query.all()
    for s in sessions:
        session_data = {
            'id': s.id,
            'user_id': s.user_id,
            'session_token': getattr(s, 'session_token', ''),
            'ip_address': getattr(s, 'ip_address', None),
            'user_agent': getattr(s, 'user_agent', None),
            'created_at': s.created_at.isoformat() if hasattr(s, 'created_at') and s.created_at else None,
            'last_seen': s.last_seen.isoformat() if hasattr(s, 'last_seen') and s.last_seen else None
        }
        data_export['sessions'].append(session_data)
    print(f"   ✅ {len(sessions)} sessions exportées")
    
    # Payments
    payments = Payment.query.all()
    for p in payments:
        payment_data = {
            'id': p.id,
            'user_id': p.user_id,
            'plan': getattr(p, 'plan', 'free'),
            'duration': getattr(p, 'duration', 'monthly'),
            'amount': getattr(p, 'amount', 0),
            'reference': getattr(p, 'reference', ''),
            'status': getattr(p, 'status', 'pending'),
            'created_at': p.created_at.isoformat() if hasattr(p, 'created_at') and p.created_at else None,
            'paid_at': p.paid_at.isoformat() if hasattr(p, 'paid_at') and p.paid_at else None
        }
        data_export['payments'].append(payment_data)
    print(f"   ✅ {len(payments)} paiements exportés")
    
    # Download tokens
    tokens = DownloadToken.query.all()
    for t in tokens:
        token_data = {
            'id': t.id,
            'file_id': t.file_id,
            'token': getattr(t, 'token', ''),
            'created_at': t.created_at.isoformat() if hasattr(t, 'created_at') and t.created_at else None,
            'expires_at': t.expires_at.isoformat() if hasattr(t, 'expires_at') and t.expires_at else None,
            'used': getattr(t, 'used', False)
        }
        data_export['tokens'].append(token_data)
    print(f"   ✅ {len(tokens)} tokens exportés")
    
    # Promo codes
    promos = PromoCode.query.all()
    for promo in promos:
        promo_data = {
            'id': promo.id,
            'code': getattr(promo, 'code', ''),
            'discount_percent': getattr(promo, 'discount_percent', 0),
            'max_uses': getattr(promo, 'max_uses', 0),
            'current_uses': getattr(promo, 'current_uses', 0),
            'valid_from': promo.valid_from.isoformat() if hasattr(promo, 'valid_from') and promo.valid_from else None,
            'valid_until': promo.valid_until.isoformat() if hasattr(promo, 'valid_until') and promo.valid_until else None,
            'is_active': getattr(promo, 'is_active', True)
        }
        data_export['promos'].append(promo_data)
    print(f"   ✅ {len(promos)} codes promo exportés")
    
    # Shared links
    links = SharedLink.query.all()
    for link in links:
        link_data = {
            'id': link.id,
            'file_id': link.file_id,
            'share_token': getattr(link, 'share_token', ''),
            'password_hash': getattr(link, 'password_hash', None),
            'expires_at': link.expires_at.isoformat() if hasattr(link, 'expires_at') and link.expires_at else None,
            'created_at': link.created_at.isoformat() if hasattr(link, 'created_at') and link.created_at else None,
            'max_downloads': getattr(link, 'max_downloads', 0),
            'current_downloads': getattr(link, 'current_downloads', 0)
        }
        data_export['links'].append(link_data)
    print(f"   ✅ {len(links)} liens partagés exportés")

# Sauvegarder en JSON
export_file = 'database/export_data.json'
with open(export_file, 'w', encoding='utf-8') as f:
    json.dump(data_export, f, indent=2, ensure_ascii=False)

print(f"\n✅ Données exportées dans : {export_file}")
print(f"📊 Total : {sum(len(v) for v in data_export.values())} enregistrements")
print("\n" + "=" * 70)
print("✅ EXPORT TERMINÉ")
print("=" * 70)
print("\nProchaine étape : Lancer import_to_postgres.py")
