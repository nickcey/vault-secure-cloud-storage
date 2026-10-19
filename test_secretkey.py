#!/usr/bin/env python3
"""Test si SECRET_KEY est bien chargée depuis .env"""

from app import app

secret_key = app.config['SECRET_KEY']

print(f"\n🔑 Test SECRET_KEY")
print(f"{'='*60}")

if len(secret_key) == 64:  # 32 bytes hex = 64 caractères
    print(f"✅ SECRET_KEY chargée depuis .env")
    print(f"   Clé : {secret_key[:16]}...{secret_key[-16:]}")
    print(f"   Longueur : {len(secret_key)} caractères")
else:
    print(f"⚠️  SECRET_KEY temporaire (générée automatiquement)")
    print(f"   Longueur : {len(secret_key)} caractères")
    print(f"\n💡 Le fichier .env existe mais n'est peut-être pas au bon endroit")
