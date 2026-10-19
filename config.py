import os
import secrets

class Config:
    # ══════════════════════════════════════════════════════════════
    # SÉCURITÉ - SECRET_KEY
    # ══════════════════════════════════════════════════════════════
    # Lire depuis variable d'environnement (.env)
    # Si absente, générer une clé aléatoire temporaire (DEV uniquement)
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        # En développement, générer une clé temporaire
        SECRET_KEY = secrets.token_urlsafe(32)
        print("⚠️  WARNING: Utilisation d'une SECRET_KEY temporaire.")
        print("   Créez un fichier .env avec SECRET_KEY pour la persistance.")
    
    # ══════════════════════════════════════════════════════════════
    # BASE DE DONNÉES - SQLite (temporairement forcé)
    # ══════════════════════════════════════════════════════════════
    # PostgreSQL désactivé temporairement (problème d'authentification)
    # VAULT_DB_PATH permet aux tests d'utiliser une base temporaire
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.environ.get('VAULT_DB_PATH', os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        'database',
        'cloud.db'
    ))
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Blobs chiffrés stockés HORS du dossier static (non servis publiquement)
    UPLOAD_FOLDER = os.environ.get('VAULT_UPLOAD_FOLDER', os.path.join(
        os.path.abspath(os.path.dirname(__file__)), 'storage', 'uploads'))
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024 * 1024  # 10 Go max
    
    # ══════════════════════════════════════════════════════════════
    # SÉCURITÉ DES SESSIONS (HTTPS/Production)
    # ══════════════════════════════════════════════════════════════
    # Cookies sécurisés : uniquement transmis en HTTPS (production)
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_ENV') == 'production'
    SESSION_COOKIE_HTTPONLY = True  # Protection XSS
    SESSION_COOKIE_SAMESITE = 'Lax'  # Protection CSRF supplémentaire
    SESSION_COOKIE_NAME = 'session'  # Nom explicite du cookie
    SESSION_TYPE = 'filesystem'  # Ou 'null' pour cookie-based (par défaut)
    
    # Durée de vie des sessions : 5 minutes d'inactivité
    PERMANENT_SESSION_LIFETIME = 300
    
    # ══════════════════════════════════════════════════════════════
    # PROTECTION CSRF (Cross-Site Request Forgery)
    # ══════════════════════════════════════════════════════════════
    WTF_CSRF_ENABLED = True  # Protection active (templates + csrf.js déjà prêts)
    WTF_CSRF_CHECK_DEFAULT = True
    
    # ══════════════════════════════════════════════════════════════
    # EMAIL - Configuration SMTP
    # ══════════════════════════════════════════════════════════════
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # ══════════════════════════════════════════════════════════════
    # CAMPAY - Payment Gateway
    # ══════════════════════════════════════════════════════════════
    CAMPAY_APP_USERNAME = os.environ.get('CAMPAY_APP_USERNAME')
    CAMPAY_APP_PASSWORD = os.environ.get('CAMPAY_APP_PASSWORD')
    CAMPAY_BASE_URL = os.environ.get('CAMPAY_BASE_URL', 'https://demo.campay.net/api')

PLANS = {
    'free': {
        'name': 'Gratuit',
        'quota': 1_610_612_736,
        'price_monthly': 0,
        'price_yearly': 0,
        'display_price_monthly': 0,
        'display_price_yearly': 0,
        'duration_days_monthly': 0,
        'duration_days_yearly': 0,
        'description': 'Pour débuter',
        'reduction_size': 0,
        'reduction_yearly': 0
    },
    'starter': {
        'name': 'Starter',
        'quota': 107_374_182_400,
        'price_monthly': 10,
        'price_yearly': 10,
        'display_price_monthly': 2000,
        'display_price_yearly': 20000,
        'duration_days_monthly': 30,
        'duration_days_yearly': 365,
        'description': 'Pour un usage personnel',
        'reduction_size': 0,
        'reduction_yearly': 17
    },
    'pro': {
        'name': 'Pro',
        'quota': 536_870_912_000,
        'price_monthly': 10,
        'price_yearly': 20,
        'display_price_monthly': 8500,
        'display_price_yearly': 85000,
        'duration_days_monthly': 30,
        'duration_days_yearly': 365,
        'description': 'Pour un usage intensif',
        'reduction_size': 15,
        'reduction_yearly': 17
    },
    'premium': {
        'name': 'Premium',
        'quota': 1_099_511_627_776,
        'price_monthly': 15,
        'price_yearly': 25,
        'display_price_monthly': 15000,
        'display_price_yearly': 150000,
        'duration_days_monthly': 30,
        'duration_days_yearly': 365,
        'description': 'Pour un usage professionnel',
        'reduction_size': 25,
        'reduction_yearly': 17
    },
}