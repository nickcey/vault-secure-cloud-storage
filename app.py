"""
Vault Secure Cloud Storage — SERVEUR ZERO-KNOWLEDGE
====================================================
Le serveur agit comme un coffre à octets aveugle :
- il ne voit jamais le mot de passe (PBKDF2 dérivé dans le navigateur, seuls 256 bits
  de la valeur d'authentification sont envoyés et hachés en Argon2id) ;
- il ne voit jamais de clé privée en clair (stockée chiffrée AES-GCM côté client) ;
- il ne voit jamais de clé de fichier en clair (enveloppée RSA-OAEP côté client) ;
- il ne voit jamais de nom de fichier en clair (métadonnées chiffrées AES-GCM/HKDF) ;
- les liens de partage transmettent la clé de fichier dans le fragment (#) de l'URL,
  qui ne quitte jamais le navigateur du destinataire.
"""

from flask import (Flask, render_template, request, redirect, url_for, flash,
                   session, send_file, jsonify, g, Response)
from flask_mail import Mail, Message
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, CSRFError, validate_csrf
from dotenv import load_dotenv

load_dotenv()

from config import Config, PLANS
from database.models import (db, User, FileMetadata, ActivityLog, ActiveSession,
                             Payment, DownloadTicket, PromoCode, SharedLink,
                             Delegation, FileShare, RecoveryShare, RecoveryRequest,
                             RecoveryApproval)
from modules.argon2_auth import hash_auth_value, verify_auth_value
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from modules.payment import initiate_payment, check_payment_status
import modules.payment as payment_module
from modules.email_templates import render as render_email
from i18n_en import translate as i18n_translate, js_payload as i18n_payload
from modules import pre as umbral_pre_srv
from translations import t
from datetime import datetime, timedelta
import json
import hmac
import time
import os
import secrets
import uuid
import hashlib

# ══════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════
import logging
from logging.handlers import RotatingFileHandler

PBKDF2_ITERATIONS = 600000


def setup_logging(flask_app):
    if not flask_app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        handler = RotatingFileHandler('logs/vault.log', maxBytes=10240000, backupCount=10)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        handler.setLevel(logging.INFO)
        flask_app.logger.addHandler(handler)
        flask_app.logger.setLevel(logging.INFO)
        flask_app.logger.info('Vault startup')


def _add_missing_columns():
    """Ajoute les colonnes récentes à une base SQLite existante (sans perte de données)."""
    from sqlalchemy import inspect, text
    insp = inspect(db.engine)
    wanted = {
        'users': [('recovery_auth_hash', 'VARCHAR(200)'), ('umbral_public_key', 'TEXT'),
                  ('verifying_key', 'TEXT'), ('encrypted_umbral_keys', 'TEXT'),
                  ('shamir_wrapped_key', 'TEXT'), ('shamir_auth_hash', 'VARCHAR(200)'),
                  ('shamir_configured_at', 'DATETIME'), ('folder_index', 'TEXT'),
                  ('folder_index_key', 'TEXT'), ('folder_index_version', 'INTEGER DEFAULT 0')],
        'files': [('umbral_capsule', 'TEXT'), ('umbral_ciphertext', 'TEXT')],
        'recovery_shares': [('status', "VARCHAR(20) DEFAULT 'pending'"), ('responded_at', 'DATETIME')],
        'file_shares': [('folder_label', 'TEXT')],
    }
    tables = insp.get_table_names()
    for table, columns in wanted.items():
        if table not in tables:
            continue
        existing = {c['name'] for c in insp.get_columns(table)}
        for name, sqltype in columns:
            if name not in existing:
                with db.engine.begin() as conn:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {sqltype}'))
    # La taille réelle et l'empreinte du contenu en clair ne doivent pas rester
    # lisibles par le serveur (elles annuleraient le remplissage et permettraient
    # de reconnaître un fichier connu) : elles vivent dans les métadonnées chiffrées.
    with db.engine.begin() as conn:
        conn.execute(text('UPDATE files SET original_size = 0, content_sha256 = NULL '
                          'WHERE original_size != 0 OR content_sha256 IS NOT NULL'))


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024 * 1024
    db.init_app(app)
    with app.app_context():
        db.create_all()
        _add_missing_columns()
        # Chaque démarrage du serveur ferme toutes les sessions : après un arrêt (Ctrl+C),
        # il faut se reconnecter, même si le navigateur a gardé son cookie.
        ActiveSession.query.delete()
        db.session.commit()
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    setup_logging(app)
    return app


app = create_app()
mail = Mail(app)
csrf = CSRFProtect(app)

limiter = Limiter(
    get_remote_address, app=app,
    default_limits=["2000 per day", "500 per hour"],
    storage_uri="memory://", strategy="fixed-window", headers_enabled=True,
)

EXCLUDED_ROUTES = ['static', 'payment_webhook', 'share_download', 'set_language', 'copy_page', 'favicon', 'web_manifest', 'service_worker', 'i18n_script']
LEGACY_INLINE_ENDPOINTS = {'plans_page', 'subscribe', 'payment_pending', 'activity_page',
                           'user_activity'}

def _utcnow():
    return datetime.utcnow()


def _dev_mode():
    """En développement seulement, le code OTP est renvoyé si l'e-mail ne part pas."""
    return os.environ.get('FLASK_ENV') != 'production'


# ══════════════════════════════════════════════════════════════
# CSP STRICT + HEADERS
# ══════════════════════════════════════════════════════════════

@app.before_request
def force_https():
    if os.environ.get('FLASK_ENV') == 'production':
        if request.url.startswith('http://'):
            return redirect(request.url.replace('http://', 'https://', 1), code=301)


# Pages réservées aux visiteurs non connectés : une fois connecté, y revenir
# (bouton « Retour » du navigateur, favori...) renvoie à l'espace de l'utilisateur.
GUEST_ONLY = {'login', 'login_page', 'signup', 'signup_page', 'verify_otp', 'verify_signup_otp',
              'recover_page', 'recover_contacts_page'}


@app.before_request
def guest_pages_redirect():
    if request.method != 'GET':
        return None
    if int(time.time()) - session.get('last_activity', 0) > 1800:
        return None                      # session expirée : la page de connexion s'affiche
    if request.endpoint in GUEST_ONLY and session.get('user_id'):
        user = current_user()
        if user:
            return redirect(url_for('admin_dashboard') if user.is_admin else url_for('dashboard'))
    if request.endpoint == 'admin_login' and session.get('admin_authenticated'):
        return redirect(url_for('admin_dashboard'))
    return None


@app.after_request
def add_security_headers(response):
    # Pages HTML jamais conservées par le navigateur : le bouton « Retour » redemande
    # la page au serveur, qui décide (OTP déjà utilisé, session terminée...). Évite aussi
    # de réafficher une page de l'espace privé après la déconnexion.
    if response.mimetype == 'text/html':
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    if os.environ.get('FLASK_ENV') == 'production' or request.is_secure:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains; preload'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    # Pages historiques (abonnement, administration...) encore écrites avec des scripts
    # inline : CSP assouplie pour elles seulement. Les pages qui manipulent les clés
    # (connexion, inscription, fichiers, partage, récupération) restent en script-src 'self'.
    endpoint = request.endpoint or ''
    legacy = endpoint.startswith('admin') or endpoint in LEGACY_INLINE_ENDPOINTS
    if legacy:
        script_src = "script-src 'self' 'unsafe-inline'; "
    else:
        # Scripts inline du design autorisés uniquement avec le nonce de la requête :
        # un script injecté (XSS) n'a pas ce nonce et reste bloqué.
        # 'wasm-unsafe-eval' : autorise seulement la compilation du module WebAssembly
        # Umbral servi par Vault (n'autorise pas eval() sur du texte JavaScript).
        script_src = "script-src 'self' 'nonce-%s' 'wasm-unsafe-eval'; " % g.get('csp_nonce', '')
    csp = (
        "default-src 'self'; "
        + script_src +
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "connect-src 'self'; "
        "worker-src 'self'; "
        "frame-ancestors 'none';"
    )
    response.headers['Content-Security-Policy'] = csp
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    return response


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
            request.headers.get('X-CSRFToken') or request.headers.get('X-CSRF-Token'):
        return jsonify(error='Session expirée ou requête invalide (CSRF). Rechargez la page.'), 400
    flash('Requête invalide (protection CSRF). Réessayez.', 'error')
    return redirect(request.referrer or url_for('login'))


# ══════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════

def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} o"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} Ko"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} Mo"
    elif size_bytes < 1024 * 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} Go"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024 * 1024):.1f} To"


def generate_otp():
    return str(secrets.randbelow(900000) + 100000)


def _app_url(path=''):
    """Adresse absolue de Vault pour les liens des courriels."""
    try:
        return request.url_root.rstrip('/') + path
    except RuntimeError:
        return path


def _mail_language(to):
    """Langue du destinataire : celle de son compte, sinon celle de la page en cours."""
    u = User.query.filter_by(email=to).first()
    if u and u.language:
        return u.language
    try:
        return session.get('language', 'fr')
    except RuntimeError:   # hors requête
        return 'fr'


def send_vault_mail(to, subject, **content):
    """Courriel aux couleurs de Vault (HTML + texte). Lève une exception si l'envoi échoue."""
    code = content.get('code')
    if code and 'copy_url' not in content:
        # Valeur après « # » : jamais envoyée au serveur quand on ouvre le lien
        content['copy_url'] = _app_url('/copier') + ('#c=' if str(code).isdigit() else '#p=') + str(code)
    lang = _mail_language(to)
    if lang == 'en':
        subject = i18n_translate(subject)
        for k in ('title', 'greeting', 'code_label', 'code_note', 'notice', 'preheader', 'text_label'):
            if content.get(k):
                content[k] = i18n_translate(content[k])
        content['paragraphs'] = [i18n_translate(x) for x in content.get('paragraphs', [])]
        if content.get('button'):
            content['button'] = (i18n_translate(content['button'][0]), content['button'][1])
    html, text = render_email(lang=lang, **content)
    msg = Message(subject, sender=app.config['MAIL_USERNAME'], recipients=[to])
    msg.body = text
    msg.html = html
    mail.send(msg)


def send_otp_email(email, otp_code):
    send_vault_mail(
        email, f'{otp_code} est votre code de connexion Vault',
        title='Votre code de connexion',
        paragraphs=['Saisissez ce code sur la page de connexion pour accéder à votre coffre Vault.'],
        code=otp_code, code_label='Code de vérification', text_label='Votre code de vérification est',
        code_note='Valable 2 minutes · usage unique',
        notice="Si vous n'êtes pas à l'origine de cette connexion, ne communiquez ce code à personne "
               "et changez votre mot de passe.",
        preheader=f'Votre code de connexion : {otp_code}')


def current_user():
    uid = session.get('user_id')
    if not uid:
        return None
    return User.query.get(uid)


def log_activity(user_id, action, file_uuid=None):
    db.session.add(ActivityLog(user_id=user_id, action=action, file_uuid=file_uuid))


def verify_csrf():
    token = request.headers.get('X-CSRFToken') or request.form.get('csrf_token')
    if not token:
        return False
    try:
        validate_csrf(token)
        return True
    except Exception:
        return False


def fake_salt_for(kind, email):
    """Faux sel déterministe par HMAC pour un email inconnu (anti-énumération)."""
    secret = (app.config.get('SECRET_KEY') or 'vault-dev-secret').encode()
    return hmac.new(secret, f"{kind}:{email}".encode(), hashlib.sha256).digest()[:16].hex()


@app.before_request
def load_language():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        g.lang = (user.language or 'fr') if user else session.get('language', 'fr')
    else:
        g.lang = session.get('language', 'fr')


@app.context_processor
def inject_language():
    return dict(t=lambda key: t(key, g.lang), lang=g.lang,
                csp_nonce=g.get('csp_nonce', ''))


@app.before_request
def make_csp_nonce():
    g.csp_nonce = secrets.token_urlsafe(16)


@app.before_request
def check_session_timeout():
    if request.endpoint in EXCLUDED_ROUTES:
        return
    if 'user_id' in session:
        # Session fermée côté serveur (redémarrage, déconnexion à distance depuis « Sessions ») :
        # le cookie ne suffit plus.
        token = session.get('session_token')
        if not token or not ActiveSession.query.filter_by(session_token=token).first():
            saved_lang = session.get('language')
            session.clear()
            if saved_lang:
                session['language'] = saved_lang
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Session expirée, reconnectez-vous.'}), 401
            resp = redirect(url_for('login'))
            resp.headers['Clear-Site-Data'] = '"storage"'   # efface aussi la clé privée locale
            return resp
        if int(time.time()) - session.get('last_activity', 0) > 1800:
            saved_lang = session.get('language')
            session.clear()
            if saved_lang:
                session['language'] = saved_lang
            return redirect(url_for('login'))
        session['last_activity'] = int(time.time())
        # Mot de passe temporaire : l'utilisateur doit d'abord choisir le sien
        # (c'est à ce moment que ses clés sont créées dans le navigateur).
        if request.endpoint not in TEMP_PASSWORD_ALLOWED:
            user = current_user()
            if user and user.is_temp_password and not user.is_admin:
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'Choisissez d\'abord votre mot de passe.'}), 403
                return redirect(url_for('change_password_page'))


TEMP_PASSWORD_ALLOWED = {'change_password_page', 'api_setup_keys', 'get_salt', 'logout',
                         'static', 'set_language', 'copy_page', 'favicon', 'web_manifest', 'service_worker', 'i18n_script'}


# ══════════════════════════════════════════════════════════════
# SÉL PBKDF2 (anti-énumération par faux sel déterministe)
# ══════════════════════════════════════════════════════════════

@app.route('/get-salt', methods=['POST'])
@csrf.exempt
@limiter.limit("30 per minute")
def get_salt():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if user:
        return jsonify({'salt': user.salt, 'iterations': PBKDF2_ITERATIONS})
    return jsonify({'salt': fake_salt_for('no-user', email), 'iterations': PBKDF2_ITERATIONS})


# ══════════════════════════════════════════════════════════════
# INSCRIPTION (chiffrement 100 % côté client)
# ══════════════════════════════════════════════════════════════

@app.route('/signup', methods=['GET', 'POST'])
@limiter.limit("5 per hour", methods=['POST'])
def signup():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        if not username or not email:
            flash('Tous les champs sont obligatoires', 'error')
            return redirect(url_for('signup'))
        if '@' not in email or '.' not in email.split('@')[-1]:
            flash('Adresse email invalide', 'error')
            return redirect(url_for('signup'))
        if User.query.filter_by(email=email).first():
            flash('Cet email est déjà utilisé', 'error')
            return redirect(url_for('signup'))

        otp = generate_otp()
        session['signup_username'] = username
        session['signup_email'] = email
        session['signup_otp'] = otp
        session['signup_otp_expiry'] = int(time.time()) + 120

        try:
            send_vault_mail(
                email, f'{otp} est votre code de vérification Vault',
                title='Bienvenue sur Vault',
                greeting=f'Bonjour {username},',
                paragraphs=['Merci de votre inscription. Pour confirmer votre adresse email, '
                            "saisissez ce code sur la page d'inscription."],
                code=otp, code_label='Code de vérification', text_label='Votre code de vérification est',
                code_note='Valable 2 minutes · usage unique',
                notice="Si vous n'avez pas demandé à créer un compte Vault, ignorez simplement ce message.",
                preheader=f'Votre code de vérification : {otp}')
            flash('Un code de vérification a été envoyé à votre adresse email.', 'info')
        except Exception as e:
            app.logger.error(f'Échec envoi OTP inscription : {e}')
            if not _dev_mode():
                flash("Impossible d'envoyer l'e-mail de vérification.", 'error')
                return redirect(url_for('signup'))
            flash(f'Erreur envoi email. Code : {otp}', 'info')
        return redirect(url_for('verify_signup_otp'))

    return render_template('signup.html')


def _clear_signup_session():
    for key in ['signup_email', 'signup_username', 'signup_otp', 'signup_otp_expiry']:
        session.pop(key, None)


@app.route('/verify-signup-otp', methods=['GET', 'POST'])
def verify_signup_otp():
    """Comme avant : code OTP -> compte créé -> mot de passe temporaire envoyé par email.
    Le mot de passe temporaire sert UNIQUEMENT à se connecter la première fois : aucune clé
    n'est créée avec lui. Les clés sont générées dans le navigateur quand l'utilisateur
    choisit son propre mot de passe (page « Changer votre mot de passe »)."""
    if 'signup_email' not in session:
        return redirect(url_for('signup'))

    if request.method == 'POST':
        otp_code = request.form.get('otp_code') or ''
        if int(time.time()) > session.get('signup_otp_expiry', 0):
            flash('Code OTP expiré. Recommencez l\'inscription.', 'error')
            _clear_signup_session()
            return redirect(url_for('signup'))
        if not hmac.compare_digest(str(otp_code), str(session.get('signup_otp', ''))):
            flash('Code OTP invalide', 'error')
            return redirect(url_for('verify_signup_otp'))

        email = session['signup_email']
        username = session.get('signup_username') or email.split('@')[0]
        if User.query.filter_by(email=email).first():
            flash('Cet email est déjà utilisé', 'error')
            _clear_signup_session()
            return redirect(url_for('signup'))

        # Mot de passe temporaire : on stocke seulement le haché Argon2id de sa valeur
        # d'authentification (même calcul que le navigateur à la connexion).
        # 12 caractères sans signes ambigus (0/O, 1/l/I) : facile à recopier depuis le courriel
        alphabet = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789'
        temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))
        salt = secrets.token_bytes(16)
        raw = PBKDF2HMAC(algorithm=hashes.SHA256(), length=64, salt=salt,
                         iterations=PBKDF2_ITERATIONS).derive(temp_password.encode())

        candidate, i = username, 1
        while User.query.filter_by(username=candidate).first():
            candidate, i = f"{username}{i}", i + 1

        user = User(
            username=candidate, email=email,
            auth_hash=hash_auth_value(raw[32:].hex()), salt=salt.hex(),
            public_key='', encrypted_private_key='{}',
            is_temp_password=True,
            plan='free', quota=1610612736,
            language=session.get('language', 'fr'),
        )
        db.session.add(user)
        db.session.commit()
        _clear_signup_session()

        try:
            send_vault_mail(
                email, 'Votre compte Vault est créé',
                title='Votre compte est créé',
                greeting=f'Bonjour {username},',
                paragraphs=['Votre compte Vault a été créé avec succès. Connectez-vous avec ce mot de passe '
                            'temporaire : vous choisirez ensuite votre propre mot de passe.',
                            "C'est à ce moment-là que vos clés de chiffrement seront créées, dans votre "
                            "navigateur : le mot de passe temporaire ne protège encore aucune donnée."],
                code=temp_password, code_label='Mot de passe temporaire',
                text_label='Votre mot de passe temporaire est',
                button=('Se connecter', _app_url('/login')),
                preheader='Votre mot de passe temporaire pour vous connecter à Vault')
        except Exception as e:
            app.logger.error(f'Échec envoi mot de passe temporaire : {e}')
            if _dev_mode():
                flash(f'Erreur envoi email. Mot de passe temporaire : {temp_password}', 'info')

        session['user_id'] = user.id
        session['last_activity'] = int(time.time())
        token = secrets.token_urlsafe(32)
        session['session_token'] = token
        db.session.add(ActiveSession(
            user_id=user.id, session_token=token, ip_address=request.remote_addr,
            user_agent=(request.headers.get('User-Agent') or '')[:200]))
        log_activity(user.id, 'Inscription')
        db.session.commit()

        flash('Compte créé avec succès ! Vous devez changer votre mot de passe.', 'success')
        return redirect(url_for('change_password_page'))

    return render_template('verify_otp_signup.html', expiry=session.get('signup_otp_expiry', 0))


@app.route('/api/setup-keys', methods=['POST'])
def api_setup_keys():
    """Premier mot de passe choisi : le navigateur envoie la preuve du mot de passe temporaire
    et le coffre (clés générées et chiffrées dans le navigateur)."""
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    if not user.is_temp_password:
        return jsonify({'error': 'Le compte est déjà configuré.'}), 400
    data = request.get_json(force=True, silent=True) or {}
    if not verify_auth_value(data.get('current_auth_value') or '', user.auth_hash):
        return jsonify({'error': 'Mot de passe temporaire incorrect'}), 401
    fields = ['auth_value', 'recovery_auth_value', 'salt', 'public_key',
              'encrypted_private_key', 'recovery_wrapped_key']
    if not all(data.get(f) for f in fields):
        return jsonify({'error': 'Données de chiffrement manquantes'}), 400
    try:
        user.auth_hash = hash_auth_value(data['auth_value'])
        user.recovery_auth_hash = hash_auth_value(data['recovery_auth_value'])
    except Exception:
        return jsonify({'error': 'Valeur d\'authentification invalide'}), 400
    user.salt = data['salt']
    user.public_key = data['public_key']
    user.encrypted_private_key = data['encrypted_private_key']
    user.recovery_wrapped_key = data['recovery_wrapped_key']
    user.is_temp_password = False
    log_activity(user.id, 'Mot de passe choisi')
    db.session.commit()
    return jsonify({'ok': True})


# ══════════════════════════════════════════════════════════════
# LOGIN (2FA e-mail conservée) — le serveur ne reçoit pas le mot de passe
# ══════════════════════════════════════════════════════════════

@app.route('/login', methods=['GET', 'POST'])
@csrf.exempt
@limiter.limit("10 per minute", methods=['POST'])
def login():
    if request.method == 'GET':
        if current_user():
            return redirect(url_for('dashboard'))
        return render_template('login.html')
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    auth_value_hex = data.get('auth_value')

    if not email or not auth_value_hex:
        return jsonify({'error': 'Requête invalide'}), 400

    user = User.query.filter_by(email=email).first()
    if user is None or not verify_auth_value(auth_value_hex, user.auth_hash):
        app.logger.warning(f'Failed login attempt for {email} from {request.remote_addr}')
        return jsonify({'error': 'Email ou mot de passe incorrect'}), 401

    if user.is_suspended:
        return jsonify({'error': 'Votre compte a été suspendu. Contactez le support.'}), 403
    if user.is_admin:
        return jsonify({'error': 'Accès refusé. Utilisez le portail administrateur.'}), 403

    session['pending_user_id'] = user.id
    session['pending_auth_ok'] = True
    session['otp_attempts'] = 0
    if not _send_login_otp(user):
        return jsonify({'error': "Impossible d'envoyer le code par e-mail."}), 500
    return jsonify({'ok': True, 'next': url_for('verify_otp')})


def _send_login_otp(user):
    """Nouveau code de connexion. En développement, si l'email ne part pas, le code
    est affiché sur la page suivante (comme avant)."""
    otp = generate_otp()
    user.otp_secret = otp
    user.otp_expiry = int(time.time()) + 120
    db.session.commit()
    try:
        send_otp_email(user.email, otp)
        flash('Un code de vérification a été envoyé à votre adresse email', 'info')
    except Exception as e:
        app.logger.error(f'Failed to send OTP email: {e}')
        if not _dev_mode():
            return False
        print(f"\n{'='*60}\nCODE OTP POUR {user.email}\n   Code : {otp}\n{'='*60}\n")
        flash(f'Erreur envoi email. Code affiché dans le terminal : {otp}', 'info')
    return True


@app.route('/verify-otp', methods=['GET', 'POST'])
@csrf.exempt
def verify_otp():
    user_id = session.get('pending_user_id')
    if request.method == 'GET':
        if not user_id or not session.get('pending_auth_ok'):
            return redirect(url_for('login'))
        user = User.query.get(user_id)
        if not user:
            return redirect(url_for('login'))
        return render_template('verify_otp.html', expiry=user.otp_expiry)

    data = request.get_json(force=True, silent=True) or {}
    if not user_id or not session.get('pending_auth_ok'):
        return jsonify({'error': 'Session de connexion expirée. Reconnectez-vous.', 'restart': True}), 400
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Utilisateur introuvable', 'restart': True}), 400

    if data.get('action') == 'resend':
        if int(time.time()) > (user.otp_expiry or 0):
            session['otp_attempts'] = 0
            if not _send_login_otp(user):
                return jsonify({'error': "Impossible d'envoyer le code par e-mail."}), 500
        else:
            flash('Un code est déjà actif. Attendez son expiration.', 'info')
        return jsonify({'ok': True, 'reload': True})

    otp_code = str(data.get('otp_code') or '')
    if int(time.time()) > (user.otp_expiry or 0):
        return jsonify({'error': 'Code OTP expiré. Demandez un nouveau code.'}), 400
    session['otp_attempts'] = session.get('otp_attempts', 0) + 1
    if session['otp_attempts'] > 3:
        session.pop('pending_user_id', None)
        session.pop('pending_auth_ok', None)
        session.pop('otp_attempts', None)
        return jsonify({'error': 'Trop de tentatives. Veuillez vous reconnecter.', 'restart': True}), 400
    if not hmac.compare_digest(otp_code, str(user.otp_secret or '')):
        remaining = 3 - session['otp_attempts']
        return jsonify({'error': f'Code OTP invalide. {remaining} tentative(s) restante(s).'}), 400

    session.pop('pending_user_id', None)
    session.pop('pending_auth_ok', None)
    session.pop('otp_attempts', None)
    session['user_id'] = user.id
    session['last_activity'] = int(time.time())
    user.otp_secret = ''          # code à usage unique
    user.otp_expiry = 0
    token = secrets.token_urlsafe(32)
    session['session_token'] = token
    if session.get('language') in ('fr', 'en'):
        user.language = session['language']

    db.session.add(ActiveSession(
        user_id=user.id, session_token=token,
        ip_address=request.remote_addr,
        user_agent=(request.headers.get('User-Agent') or '')[:200]))
    log_activity(user.id, 'Connexion')
    db.session.commit()

    if user.is_temp_password:
        # Pas encore de clés : elles seront créées avec le mot de passe choisi.
        return jsonify({'ok': True, 'must_change_password': True})

    # Clé privée CHIFFRÉE (AES-GCM) : le navigateur la déchiffre avec la clé
    # de compte qu'il a gardée depuis la page de connexion.
    return jsonify({
        'ok': True,
        'encrypted_private_key': user.encrypted_private_key,
        'encrypted_private_key_format': 'aes-gcm-account-key',
    })


# ══════════════════════════════════════════════════════════════
# PAGES PRINCIPALES
# ══════════════════════════════════════════════════════════════

@app.route('/copier')
def copy_page():
    """Page « Copier » des courriels : la valeur est après « # », jamais reçue ici."""
    return render_template('copier.html')


@app.route('/manifest.webmanifest')
def web_manifest():
    return send_file(os.path.join(app.root_path, 'static', 'manifest.webmanifest'),
                     mimetype='application/manifest+json', max_age=3600)


@app.route('/i18n/en.js')
def i18n_script():
    """Dictionnaire français -> anglais pour vault-i18n.js (le même que pour les courriels)."""
    body = 'window.VAULT_EN = ' + json.dumps(i18n_payload(), ensure_ascii=False) + ';'
    resp = app.response_class(body, mimetype='application/javascript')
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@app.route('/sw.js')
def service_worker():
    resp = send_file(os.path.join(app.root_path, 'static', 'sw.js'), mimetype='text/javascript', max_age=0)
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@app.route('/favicon.ico')
def favicon():
    return send_file(os.path.join(app.root_path, 'static', 'img', 'favicon.ico'), mimetype='image/vnd.microsoft.icon',
                     max_age=86400)


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login-page')
def login_page():
    return render_template('login.html')


@app.route('/signup-page')
def signup_page():
    return render_template('signup.html')


@app.route('/recover-page')
@app.route('/recover')
def recover_page():
    return render_template('recover.html')


@app.route('/change-password-page')
@app.route('/change-password')
def change_password_page():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    return render_template('change_password.html', user=user, temp=bool(user.is_temp_password))


def _storage_stats(user):
    """Espace occupé (tailles des blobs chiffrés : aucune information sur le contenu)."""
    used = db.session.query(db.func.coalesce(db.func.sum(FileMetadata.stored_size), 0)) \
        .filter_by(user_id=user.id, is_deleted=False).scalar() or 0
    return {
        'used_bytes': used,
        'used_space': format_size(used),
        'total_space': format_size(user.quota),
        'used_percent': min(round((used / user.quota) * 100, 1), 100) if user.quota > 0 else 0,
    }


@app.route('/dashboard')
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    return render_template('dashboard.html', user=user, stats=_storage_stats(user))


@app.route('/transfers')
def transfers_page():
    return redirect(url_for('share_list_page'))


@app.route('/api/me')
def api_me():
    """Informations du compte connecté : uniquement des données publiques ou chiffrées."""
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    return jsonify({
        'email': user.email,
        'username': user.username,
        'public_key': user.public_key,
        'encrypted_private_key': user.encrypted_private_key,
        'umbral_public_key': user.umbral_public_key,
        'verifying_key': user.verifying_key,
        'encrypted_umbral_keys': user.encrypted_umbral_keys,
        'pre_available': umbral_pre_srv.AVAILABLE,
    })


# ══════════════════════════════════════════════════════════════
# DOSSIERS : index chiffré côté client
# ══════════════════════════════════════════════════════════════
FOLDER_INDEX_MAX = 2 * 1024 * 1024


@app.route('/api/folder-index', methods=['GET', 'POST'])
@limiter.limit("120 per minute")
def api_folder_index():
    """Index des dossiers de l'utilisateur. Le serveur stocke un bloc chiffré opaque et
    sa clé enveloppée par la clé publique du compte ; il ne connaît ni les noms des
    dossiers ni le dossier de chaque fichier. Un numéro de version empêche qu'un onglet
    écrase les changements faits dans un autre."""
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    if request.method == 'GET':
        return jsonify({'index': user.folder_index, 'key': user.folder_index_key,
                        'version': user.folder_index_version or 0})
    data = request.get_json(force=True, silent=True) or {}
    index, key = data.get('index'), data.get('key')
    if not isinstance(index, str) or not index or len(index) > FOLDER_INDEX_MAX:
        return jsonify({'error': 'Index invalide'}), 400
    try:
        parsed = json.loads(index)
        if set(parsed) != {'iv', 'ct'}:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({'error': 'Index invalide'}), 400
    current = user.folder_index_version or 0
    if int(data.get('version', -1)) != current:
        return jsonify({'error': 'Index modifié ailleurs', 'version': current}), 409
    if not user.folder_index_key:
        if not isinstance(key, str) or not key or len(key) > 1024:
            return jsonify({'error': 'Clé d\'index manquante'}), 400
        user.folder_index_key = key
    user.folder_index = index
    user.folder_index_version = current + 1
    db.session.commit()
    return jsonify({'ok': True, 'version': user.folder_index_version})


@app.route('/upload-page')
@app.route('/upload', methods=['GET'])
def upload_page():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    used = db.session.query(db.func.coalesce(db.func.sum(FileMetadata.stored_size), 0)) \
        .filter_by(user_id=user.id, is_deleted=False).scalar() or 0
    return render_template('upload.html', max_space=user.quota,
                           used_space=used, used_space_formatted=format_size(used))


@app.route('/trash-page')
@app.route('/trash')
def trash_page():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    return render_template('trash.html', user=user, stats=_storage_stats(user))


@app.route('/activity-page')
@app.route('/activity')
def activity_page():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    action_filter = request.args.get('action', '')
    query = ActivityLog.query.filter_by(user_id=user.id)
    if action_filter:
        query = query.filter(ActivityLog.action.ilike(f'%{action_filter}%'))
    logs = query.order_by(ActivityLog.timestamp.desc()).limit(200).all()
    return render_template('activity.html', user=user, logs=logs, action_filter=action_filter)


@app.route('/sessions-page')
@app.route('/sessions')
def sessions_page():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    items = ActiveSession.query.filter_by(user_id=user.id) \
        .order_by(ActiveSession.last_seen.desc()).all()
    current_token = session.get('session_token')
    return render_template('sessions.html', user=user, sessions=items,
                           current_token=current_token)


@app.route('/revoke-session/<int:session_id>', methods=['POST'])
def revoke_session(session_id):
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    active = ActiveSession.query.get(session_id)
    if not active or active.user_id != user.id:
        flash('Session introuvable.', 'error')
        return redirect(url_for('sessions_page'))
    is_current = active.session_token == session.get('session_token')
    db.session.delete(active)
    db.session.commit()
    if is_current:
        saved_lang = session.get('language')
        session.clear()
        if saved_lang:
            session['language'] = saved_lang
        flash('Votre session a été révoquée. Veuillez vous reconnecter.', 'info')
        resp = redirect(url_for('login'))
        resp.headers['Clear-Site-Data'] = '"storage"'
        return resp
    flash('Session révoquée avec succès.', 'success')
    return redirect(url_for('sessions_page'))


@app.route('/settings-page')
@app.route('/settings', methods=['GET', 'POST'])
def settings_page():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    if request.method == 'POST':
        # Le mot de passe se change dans le navigateur (/api/change-password) ;
        # ici seulement le nom d'utilisateur et la langue.
        action = request.form.get('action')
        if action == 'change_username':
            new_username = request.form.get('new_username', '').strip()
            if len(new_username) < 2:
                flash('Nom d\'utilisateur trop court (min 2 caractères).', 'error')
            elif len(new_username) > 50:
                flash('Nom d\'utilisateur trop long (max 50 caractères).', 'error')
            elif User.query.filter(User.username == new_username, User.id != user.id).first():
                flash('Ce nom d\'utilisateur est déjà pris.', 'error')
            else:
                user.username = new_username
                db.session.commit()
                flash('Nom d\'utilisateur mis à jour.', 'success')
        elif action == 'change_language':
            lang = request.form.get('language')
            if lang in ('fr', 'en'):
                user.language = lang
                session['language'] = lang
                db.session.commit()
                flash('Langue mise à jour.' if lang == 'fr' else 'Language updated.', 'success')
        return redirect(url_for('settings_page'))
    used = db.session.query(db.func.coalesce(db.func.sum(FileMetadata.stored_size), 0)) \
        .filter_by(user_id=user.id, is_deleted=False).scalar() or 0
    active_links = SharedLink.query.filter(
        SharedLink.user_id == user.id,
        SharedLink.expires_at > _utcnow()).count()
    return render_template('settings.html', user=user,
                           used_space=format_size(used),
                           used_percent=min(round((used / user.quota) * 100, 1), 100) if user.quota > 0 else 0,
                           total_space=format_size(user.quota),
                           file_count=FileMetadata.query.filter_by(user_id=user.id, is_deleted=False).count(),
                           active_links=active_links)


@app.route('/share-list-page')
@app.route('/share/list')
def share_list_page():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    return render_template('share_list.html', user=user)


@app.route('/set_language/<lang>')
def set_language(lang):
    if lang in ['fr', 'en']:
        session['language'] = lang
        session.modified = True
        user = current_user()
        if user:
            user.language = lang
            db.session.commit()
    return redirect(request.referrer or url_for('login'))


# ══════════════════════════════════════════════════════════════
# UPLOAD — le client a déjà tout chiffré (AES-GCM + RSA-OAEP + HKDF)
# ══════════════════════════════════════════════════════════════

@app.route('/upload', methods=['POST'])
@limiter.limit("60 per minute")
def upload():
    # Le jeton CSRF est vérifié par CSRFProtect (en-tête X-CSRFToken ou champ csrf_token)
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401

    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'Aucun fichier'}), 400

    aes_iv = request.form.get('aes_iv')
    encrypted_file_key = request.form.get('encrypted_file_key')
    encrypted_metadata = request.form.get('encrypted_metadata')
    metadata_sha256 = request.form.get('metadata_sha256')
    # Taille réelle et empreinte du contenu en clair : jamais conservées par le serveur
    # (elles sont dans les métadonnées chiffrées). Un ancien client qui les enverrait
    # verrait ces champs ignorés.
    content_sha256 = None
    original_size = 0
    padded_size = int(request.form.get('padded_size') or 0)
    file_uuid = (request.form.get('uuid') or '').strip() or str(uuid.uuid4())

    if not all([aes_iv, encrypted_file_key, encrypted_metadata]):
        return jsonify({'error': 'Champs de chiffrement manquants'}), 400
    if original_size < 0 or padded_size <= 0:
        return jsonify({'error': 'Taille invalide'}), 400

    total_used = db.session.query(db.func.coalesce(db.func.sum(FileMetadata.stored_size), 0)) \
        .filter_by(user_id=user.id, is_deleted=False).scalar() or 0
    if total_used + padded_size > user.quota:
        return jsonify({'error': 'Quota dépassé'}), 400

    stored_filename = f"{file_uuid}.enc"
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_filename)
    file.save(upload_path)
    actual_size = os.path.getsize(upload_path)

    if actual_size < 28 or (padded_size and actual_size < padded_size):
        os.remove(upload_path)
        return jsonify({'error': 'Blob chiffré invalide'}), 400

    meta = FileMetadata(
        uuid=file_uuid,
        stored_filename=stored_filename,
        stored_size=actual_size,
        original_size=original_size,
        aes_iv=aes_iv,
        encrypted_file_key=encrypted_file_key,
        encrypted_metadata=encrypted_metadata,
        content_sha256=content_sha256,
        metadata_sha256=metadata_sha256,
        user_id=user.id,
        uploaded_at=_utcnow(),
    )
    db.session.add(meta)
    log_activity(user.id, 'Upload', file_uuid=file_uuid)
    db.session.commit()

    return jsonify({'ok': True, 'file_id': meta.id, 'uuid': file_uuid})


# ══════════════════════════════════════════════════════════════
# API FICHIERS (le navigateur déchiffre les noms et les données)
# ══════════════════════════════════════════════════════════════

@app.route('/api/files', methods=['GET'])
def api_files():
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    files = FileMetadata.query.filter_by(user_id=user.id, is_deleted=False) \
        .order_by(FileMetadata.uploaded_at.desc()).all()
    return jsonify({
        'files': [{
            'id': f.id,
            'uuid': f.uuid,
            'encrypted_metadata': f.encrypted_metadata,
            'encrypted_file_key': f.encrypted_file_key,
            'aes_iv': f.aes_iv,
            'content_sha256': f.content_sha256,
            'stored_size': f.stored_size,
            'uploaded_at': f.uploaded_at.strftime('%d/%m/%Y %H:%M'),
            'has_capsule': bool(f.umbral_capsule),
        } for f in files],
        'total_used': db.session.query(
            db.func.coalesce(db.func.sum(FileMetadata.stored_size), 0)) \
            .filter_by(user_id=user.id, is_deleted=False).scalar() or 0,
        'total_quota': user.quota,
    })


@app.route('/api/files/<int:file_id>/rename', methods=['POST'])
def api_rename(file_id):
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    data = request.get_json(force=True, silent=True) or {}
    new_meta = data.get('encrypted_metadata')
    if not new_meta:
        return jsonify({'error': 'Métadonnées manquantes'}), 400
    f = FileMetadata.query.get(file_id)
    if not f or f.user_id != user.id or f.is_deleted:
        return jsonify({'error': 'Fichier introuvable'}), 404
    f.encrypted_metadata = new_meta   # metadata_sha256 = hash du blob, inchangé
    log_activity(user.id, 'Renommage', file_uuid=f.uuid)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/files/<int:file_id>/trash', methods=['POST'])
def api_trash(file_id):
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    f = FileMetadata.query.get(file_id)
    if not f or f.user_id != user.id:
        return jsonify({'error': 'Fichier introuvable'}), 404
    f.is_deleted = True
    f.deleted_at = _utcnow()
    log_activity(user.id, 'Suppression', file_uuid=f.uuid)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/files/<int:file_id>/restore', methods=['POST'])
def api_restore(file_id):
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    f = FileMetadata.query.get(file_id)
    if not f or f.user_id != user.id:
        return jsonify({'error': 'Fichier introuvable'}), 404
    f.is_deleted = False
    f.deleted_at = None
    log_activity(user.id, 'Restauration', file_uuid=f.uuid)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/files/<int:file_id>', methods=['DELETE'])
def api_delete_permanent(file_id):
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    f = FileMetadata.query.get(file_id)
    if not f or f.user_id != user.id:
        return jsonify({'error': 'Fichier introuvable'}), 404
    path = os.path.join(app.config['UPLOAD_FOLDER'], f.stored_filename)
    if os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass
    _purge_file_relations(f)
    db.session.delete(f)
    log_activity(user.id, 'Suppression définitive', file_uuid=f.uuid)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/trash/empty', methods=['POST'])
def api_empty_trash():
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    for f in FileMetadata.query.filter_by(user_id=user.id, is_deleted=True).all():
        path = os.path.join(app.config['UPLOAD_FOLDER'], f.stored_filename)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
        _purge_file_relations(f)
        db.session.delete(f)
    log_activity(user.id, 'Vidage corbeille')
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/trash', methods=['GET'])
def api_trash_list():
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    files = FileMetadata.query.filter_by(user_id=user.id, is_deleted=True) \
        .order_by(FileMetadata.deleted_at.desc()).all()
    return jsonify({'files': [{
        'id': f.id,
        'uuid': f.uuid,
        'encrypted_metadata': f.encrypted_metadata,
        'encrypted_file_key': f.encrypted_file_key,
        'aes_iv': f.aes_iv,
        'stored_size': f.stored_size,
        'deleted_at': f.deleted_at.strftime('%d/%m/%Y %H:%M') if f.deleted_at else '',
        'expiry': (f.deleted_at + timedelta(days=30)).strftime('%d/%m/%Y') if f.deleted_at else '',
        'expired': ((f.deleted_at + timedelta(days=30)) < _utcnow()) if f.deleted_at else False,
    } for f in files]})


# ══════════════════════════════════════════════════════════════
# TÉLÉCHARGEMENT — tickets aveugles, le client déchiffre
# ══════════════════════════════════════════════════════════════

@app.route('/api/download/create/<int:file_id>', methods=['POST'])
def api_download_create(file_id):
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    f = FileMetadata.query.get(file_id)
    if not f or f.user_id != user.id or f.is_deleted:
        return jsonify({'error': 'Fichier introuvable'}), 404
    ticket = DownloadTicket(
        token=secrets.token_urlsafe(32),
        file_uuid=f.uuid, user_id=user.id,
        expiry=int(time.time()) + 600)
    db.session.add(ticket)
    log_activity(user.id, 'Téléchargement', file_uuid=f.uuid)
    db.session.commit()
    return jsonify({'token': ticket.token})


@app.route('/api/download-file/<token>')
def api_download_file(token):
    t = DownloadTicket.query.filter_by(token=token).first()
    if not t:
        return jsonify({'error': 'Ticket invalide ou expiré'}), 403
    if int(time.time()) > t.expiry:
        db.session.delete(t)
        db.session.commit()
        return jsonify({'error': 'Ticket invalide ou expiré'}), 403

    f = FileMetadata.query.filter_by(uuid=t.file_uuid).first()
    if not f or f.is_deleted:
        return jsonify({'error': 'Fichier introuvable'}), 404

    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], f.stored_filename)
    if not os.path.exists(upload_path):
        return jsonify({'error': 'Fichier manquant sur le serveur'}), 404

    # Contrôle d'intégrité côté serveur (le contrôle décisif reste le tag AES-GCM
    # vérifié par le navigateur, que le serveur ne peut pas falsifier).
    if f.metadata_sha256:
        h = hashlib.sha256()
        with open(upload_path, 'rb') as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b''):
                h.update(chunk)
        if not hmac.compare_digest(h.hexdigest(), f.metadata_sha256):
            app.logger.error(f'Intégrité compromise pour le fichier {f.uuid}')
            return jsonify({'error': 'Ce fichier a été modifié ou corrompu sur le serveur.'}), 409

    # Ticket à usage unique
    db.session.delete(t)
    db.session.commit()

    resp = send_file(upload_path, mimetype='application/octet-stream',
                     as_attachment=True, download_name=f"{f.uuid}.enc")
    return resp


@app.route('/api/download-file/<token>/sha256')
def api_download_sha256(token):
    """SHA-256 du blob chiffré : le client compare au hash stocké à l'upload."""
    t = DownloadTicket.query.filter_by(token=token).first()
    if not t:
        return jsonify({'error': 'Ticket invalide ou expiré'}), 403
    f = FileMetadata.query.filter_by(uuid=t.file_uuid).first()
    if not f or f.is_deleted:
        return jsonify({'error': 'Fichier introuvable'}), 404
    path = os.path.join(app.config['UPLOAD_FOLDER'], f.stored_filename)
    if not os.path.exists(path):
        return jsonify({'error': 'Fichier manquant'}), 404
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return jsonify({'sha256': h.hexdigest()})


# ══════════════════════════════════════════════════════════════
# PARTAGE — la clé de fichier va dans le fragment # de l'URL
# ══════════════════════════════════════════════════════════════

@app.route('/api/share/create/<int:file_id>', methods=['POST'])
def api_share_create(file_id):
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    f = FileMetadata.query.get(file_id)
    if not f or f.user_id != user.id or f.is_deleted:
        return jsonify({'error': 'Fichier introuvable'}), 404

    data = request.get_json(force=True, silent=True) or {}
    expiry_hours = int(data.get('expiry_hours') or 24)
    max_downloads = int(data.get('max_downloads') or 0)
    if expiry_hours not in (1, 6, 24, 72, 168):
        expiry_hours = 24

    token = secrets.token_urlsafe(32)
    shared = SharedLink(token=token, file_id=file_id, user_id=user.id,
                        expires_at=_utcnow() + timedelta(hours=expiry_hours),
                        max_downloads=max_downloads)
    db.session.add(shared)
    log_activity(user.id, 'Partage', file_uuid=f.uuid)
    db.session.commit()

    # La clé de fichier n'est PAS stockée côté serveur : le propriétaire l'ajoute
    # au fragment dans son navigateur (côté client) après réception de la réponse.
    return jsonify({
        'token': token,
        'url_base': url_for('share_download', token=token, _external=True),
        'expires_at': shared.expires_at.strftime('%d/%m/%Y à %H:%M'),
    })


def _get_active_share(token):
    shared = SharedLink.query.filter_by(token=token).first()
    if not shared:
        return None, 'Lien invalide ou expiré', 404
    if shared.expires_at < _utcnow():
        return None, 'Ce lien a expiré.', 404
    if shared.max_downloads > 0 and shared.download_count >= shared.max_downloads:
        return None, 'Nombre maximum de téléchargements atteint.', 404
    f = FileMetadata.query.get(shared.file_id)
    if not f or f.is_deleted:
        return None, "Le fichier n'existe plus.", 404
    return (shared, f), None, 200


@app.route('/api/share/<token>/info')
def api_share_info(token):
    shared, err, code = _get_active_share(token)
    if err:
        return jsonify({'error': err}), code
    shared, f = shared
    return jsonify({
        'file_uuid': f.uuid,
        'encrypted_meta_b64': f.encrypted_metadata,   # déchiffré avec la clé du fragment
        'aes_iv': f.aes_iv,
        'content_sha256': f.content_sha256,
        'padded_size': f.stored_size,
        'is_deleted': False,
        'filename': None,   # jamais en clair côté serveur
        'upload_date': f.uploaded_at.strftime('%d/%m/%Y'),
        'expires_at': shared.expires_at.strftime('%d/%m/%Y à %H:%M'),
        'download_count': shared.download_count,
        'max_downloads': shared.max_downloads,
    })


def _increment_and_notify(shared):
    was_first = shared.download_count == 0
    shared.download_count += 1
    db.session.commit()
    if was_first:
        try:
            owner = User.query.get(shared.user_id)
            if owner:
                send_vault_mail(
                    owner.email, 'Votre lien de partage a été utilisé - Vault',
                    title='Votre fichier partagé a été téléchargé',
                    greeting=f'Bonjour {owner.username},',
                    paragraphs=["Un fichier que vous avez partagé par lien vient d'être téléchargé pour la "
                                f"première fois (téléchargements : {shared.download_count})."],
                    notice="Si vous ne reconnaissez pas ce téléchargement, révoquez le lien depuis la page "
                           "« Transferts » de votre compte.",
                    button=('Gérer mes liens', _app_url('/share/list')))
        except Exception:
            pass


@app.route('/api/share/<token>/blob')
def api_share_blob(token):
    shared, err, code = _get_active_share(token)
    if err:
        return jsonify({'error': err}), code
    shared, f = shared

    path = os.path.join(app.config['UPLOAD_FOLDER'], f.stored_filename)
    if not os.path.exists(path):
        return jsonify({'error': 'Fichier manquant sur le serveur'}), 404

    # Vérification d'intégrité côté serveur
    if f.metadata_sha256:
        h = hashlib.sha256()
        with open(path, 'rb') as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b''):
                h.update(chunk)
        if not hmac.compare_digest(h.hexdigest(), f.metadata_sha256):
            app.logger.error(f'Intégrité compromise pour {token[:8]}')
            return jsonify({'error': "Ce fichier a été modifié ou corrompu." }), 500

    _increment_and_notify(shared)

    resp = send_file(path, mimetype='application/octet-stream', as_attachment=True,
                     download_name=f"{f.uuid}.enc")
    return resp


@app.route('/api/share/<token>/meta-hash')
def api_share_meta_hash(token):
    """Hash du blob chiffré pour vérification côté client après le transport."""
    shared, err, code = _get_active_share(token)
    if err:
        return jsonify({'error': err}), code
    shared, f = shared
    path = os.path.join(app.config['UPLOAD_FOLDER'], f.stored_filename)
    if not os.path.exists(path):
        return jsonify({'error': 'Fichier manquant'}), 404
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return jsonify({'sha256': h.hexdigest()})


@app.route('/share-download/<token>')
def share_download(token):
    """Page publique : la clé de fichier arrive dans le fragment #, jamais au serveur."""
    return render_template('share.html', token=token)


@app.route('/api/share/list')
def api_share_list():
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    links = SharedLink.query.filter_by(user_id=user.id) \
        .order_by(SharedLink.created_at.desc()).all()
    out = []
    for lnk in links:
        if lnk.expires_at < _utcnow():
            db.session.delete(lnk)
            continue
        f = FileMetadata.query.get(lnk.file_id)
        out.append({
            'id': lnk.id,
            'token': lnk.token,
            'file_uuid': f.uuid if f else None,
            'encrypted_metadata': f.encrypted_metadata if f else None,
            'encrypted_file_key': f.encrypted_file_key if f else None,
            'aes_iv': f.aes_iv if f else None,
            'content_sha256': f.content_sha256 if f else None,
            'expires_at': lnk.expires_at.strftime('%d/%m/%Y %H:%M'),
            'download_count': lnk.download_count,
            'max_downloads': lnk.max_downloads,
        })
    db.session.commit()
    return jsonify({'links': out})


@app.route('/api/share/revoke/<int:link_id>', methods=['POST'])
def api_share_revoke(link_id):
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    shared = SharedLink.query.get(link_id)
    if not shared or shared.user_id != user.id:
        return jsonify({'error': 'Lien introuvable.'}), 404
    db.session.delete(shared)
    db.session.commit()
    return jsonify({'ok': True})


# ══════════════════════════════════════════════════════════════
# MOT DE PASSE : changement / récupération 100 % client
# ══════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════
# PARTAGE ENTRE UTILISATEURS — PROXY RE-ENCRYPTION (UMBRAL)
# Le navigateur du propriétaire produit un fragment de re-chiffrement (kfrag)
# signé ; le serveur s'en sert pour transformer la capsule de la clé de fichier
# au profit du destinataire, sans jamais pouvoir la déchiffrer.
# ══════════════════════════════════════════════════════════════

def _purge_file_relations(f):
    """Supprime liens et partages d'un fichier (et les délégations devenues inutiles)."""
    SharedLink.query.filter_by(file_id=f.id).delete()
    delegation_ids = [fs.delegation_id for fs in FileShare.query.filter_by(file_id=f.id).all()]
    FileShare.query.filter_by(file_id=f.id).delete()
    db.session.flush()
    for did in set(delegation_ids):
        if not FileShare.query.filter_by(delegation_id=did).first():
            d = Delegation.query.get(did)
            if d:
                db.session.delete(d)


def _public_profile(u):
    return {'id': u.id, 'username': u.username, 'email': u.email,
            'public_key': u.public_key, 'umbral_public_key': u.umbral_public_key,
            'verifying_key': u.verifying_key}


@app.route('/api/umbral-keys', methods=['POST'])
def api_umbral_keys():
    """Enregistre les clés publiques Umbral du compte et ses clés secrètes chiffrées
    (RSA-OAEP avec la clé publique du compte : seul son navigateur peut les lire)."""
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    if user.umbral_public_key:
        return jsonify({'error': 'Clés déjà enregistrées'}), 400
    data = request.get_json(force=True, silent=True) or {}
    try:
        umbral_pre_srv.check_public_key(data.get('umbral_public_key') or '')
        umbral_pre_srv.check_public_key(data.get('verifying_key') or '')
    except umbral_pre_srv.PreError as e:
        return jsonify({'error': str(e)}), 400
    if not data.get('encrypted_umbral_keys'):
        return jsonify({'error': 'Clés secrètes chiffrées manquantes'}), 400
    user.umbral_public_key = data['umbral_public_key']
    user.verifying_key = data['verifying_key']
    user.encrypted_umbral_keys = data['encrypted_umbral_keys']
    log_activity(user.id, 'Clés de partage créées')
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/users/lookup', methods=['POST'])
@limiter.limit("30 per minute")
def api_user_lookup():
    """Clés PUBLIQUES d'un autre utilisateur (partage, contacts de confiance)."""
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    other = User.query.filter_by(email=email).first()
    if not other or other.is_admin or other.is_suspended or not other.public_key:
        return jsonify({'error': 'Aucun utilisateur Vault actif avec cette adresse.'}), 404
    if other.id == user.id:
        return jsonify({'error': 'Vous ne pouvez pas vous choisir vous-même.'}), 400
    prof = _public_profile(other)
    d = Delegation.query.filter_by(owner_id=user.id, recipient_id=other.id).first()
    prof['has_delegation'] = bool(d)
    return jsonify(prof)


@app.route('/api/files/<int:file_id>/share-user', methods=['POST'])
def api_share_with_user(file_id):
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    f = FileMetadata.query.get(file_id)
    if not f or f.user_id != user.id or f.is_deleted:
        return jsonify({'error': 'Fichier introuvable'}), 404
    data = request.get_json(force=True, silent=True) or {}
    recipient = User.query.get(int(data.get('recipient_id') or 0))
    if not recipient or recipient.id == user.id or not recipient.umbral_public_key:
        return jsonify({'error': "Ce destinataire n'a pas encore de clés de partage "
                                 "(il doit s'être connecté une fois)."}), 400
    if not user.umbral_public_key:
        return jsonify({'error': 'Vos clés de partage ne sont pas encore créées.'}), 400
    try:
        # Capsule de la clé de fichier (créée par le navigateur du propriétaire)
        if not f.umbral_capsule:
            if not data.get('capsule') or not data.get('umbral_ciphertext'):
                return jsonify({'error': 'Capsule manquante'}), 400
            umbral_pre_srv.check_capsule(data['capsule'])
            f.umbral_capsule = data['capsule']
            f.umbral_ciphertext = data['umbral_ciphertext']
        d = Delegation.query.filter_by(owner_id=user.id, recipient_id=recipient.id).first()
        if not d:
            kfrag = data.get('kfrag') or ''
            umbral_pre_srv.verify_kfrag(kfrag, user.verifying_key, user.umbral_public_key,
                                        recipient.umbral_public_key)
            d = Delegation(owner_id=user.id, recipient_id=recipient.id, kfrag=kfrag)
            db.session.add(d)
            db.session.flush()
    except umbral_pre_srv.PreError as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
    label = data.get('folder_label')
    if label is not None:
        try:
            ok_label = isinstance(label, str) and len(label) <= 4096 and set(json.loads(label)) == {'k', 'iv', 'ct'}
        except (ValueError, TypeError):
            ok_label = False
        if not ok_label:
            return jsonify({'error': 'Chemin de dossier invalide'}), 400
    fs = FileShare.query.filter_by(file_id=f.id, delegation_id=d.id).first()
    if not fs:
        fs = FileShare(file_id=f.id, delegation_id=d.id)
        db.session.add(fs)
    if label is not None:
        fs.folder_label = label
    log_activity(user.id, 'Partage utilisateur', file_uuid=f.uuid)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/shared-with-me')
def api_shared_with_me():
    """Fichiers partagés avec moi : le serveur re-chiffre chaque capsule pour moi."""
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    out = []
    for d in Delegation.query.filter_by(recipient_id=user.id).all():
        owner = User.query.get(d.owner_id)
        for fs in FileShare.query.filter_by(delegation_id=d.id).all():
            f = FileMetadata.query.get(fs.file_id)
            if not f or f.is_deleted or not f.umbral_capsule:
                continue
            try:
                cfrag = umbral_pre_srv.reencrypt(f.umbral_capsule, d.kfrag, owner.verifying_key,
                                                 owner.umbral_public_key, user.umbral_public_key)
            except umbral_pre_srv.PreError as e:
                return jsonify({'error': str(e)}), 500
            out.append({
                'share_id': fs.id, 'file_id': f.id, 'uuid': f.uuid,
                'owner': {'username': owner.username, 'email': owner.email,
                          'umbral_public_key': owner.umbral_public_key,
                          'verifying_key': owner.verifying_key},
                'capsule': f.umbral_capsule, 'umbral_ciphertext': f.umbral_ciphertext,
                'cfrag': cfrag, 'encrypted_metadata': f.encrypted_metadata,
                'content_sha256': f.content_sha256,
                'folder_label': fs.folder_label,
                'shared_at': fs.created_at.strftime('%d/%m/%Y %H:%M'),
            })
    return jsonify({'files': out})


@app.route('/api/shared-with-me/<int:share_id>/blob')
def api_shared_blob(share_id):
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    fs = FileShare.query.get(share_id)
    d = Delegation.query.get(fs.delegation_id) if fs else None
    f = FileMetadata.query.get(fs.file_id) if fs else None
    if not fs or not d or d.recipient_id != user.id or not f or f.is_deleted:
        return jsonify({'error': 'Partage introuvable ou révoqué'}), 404
    path = os.path.join(app.config['UPLOAD_FOLDER'], f.stored_filename)
    if not os.path.exists(path):
        return jsonify({'error': 'Fichier absent du stockage'}), 404
    log_activity(user.id, 'Téléchargement partagé', file_uuid=f.uuid)
    db.session.commit()
    return send_file(path, mimetype='application/octet-stream', as_attachment=False)


@app.route('/api/my-user-shares')
def api_my_user_shares():
    """Partages que j'ai accordés à d'autres utilisateurs (pour les révoquer)."""
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    out = []
    for d in Delegation.query.filter_by(owner_id=user.id).all():
        rcpt = User.query.get(d.recipient_id)
        for fs in FileShare.query.filter_by(delegation_id=d.id).all():
            f = FileMetadata.query.get(fs.file_id)
            if not f or f.is_deleted:
                continue
            out.append({'share_id': fs.id, 'uuid': f.uuid,
                        'encrypted_metadata': f.encrypted_metadata,
                        'encrypted_file_key': f.encrypted_file_key,
                        'recipient': {'username': rcpt.username, 'email': rcpt.email},
                        'shared_at': fs.created_at.strftime('%d/%m/%Y %H:%M')})
    return jsonify({'shares': out})


@app.route('/api/user-shares/<int:share_id>/revoke', methods=['POST'])
def api_revoke_user_share(share_id):
    """Révocation : le serveur ne peut plus re-chiffrer pour ce destinataire."""
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    fs = FileShare.query.get(share_id)
    d = Delegation.query.get(fs.delegation_id) if fs else None
    if not fs or not d or d.owner_id != user.id:
        return jsonify({'error': 'Partage introuvable'}), 404
    f = FileMetadata.query.get(fs.file_id)
    db.session.delete(fs)
    db.session.flush()
    if not FileShare.query.filter_by(delegation_id=d.id).first():
        db.session.delete(d)          # plus aucun fichier : la clé de re-chiffrement disparaît
    log_activity(user.id, 'Révocation partage', file_uuid=f.uuid if f else None)
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/shared-with-me')
def shared_with_me_page():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    return render_template('shared_with_me.html', user=user, stats=_storage_stats(user))


# ══════════════════════════════════════════════════════════════
# RÉCUPÉRATION PAR CONTACTS DE CONFIANCE — PARTAGE DE SECRET DE SHAMIR (2 SUR 3)
# Une clé de récupération aléatoire est découpée dans le navigateur en 3 parts,
# chacune chiffrée avec la clé publique d'un contact. Chaque contact doit d'abord
# ACCEPTER l'invitation ; ensuite, lors d'une récupération, 2 contacts sur 3
# doivent valider. Le serveur ne voit jamais une part en clair.
# ══════════════════════════════════════════════════════════════

SHAMIR_SHARES = 3          # trois contacts de confiance
SHAMIR_THRESHOLD = 2       # deux validations suffisent
SHAMIR_CONTACTS = SHAMIR_SHARES


def _accepted_shares(owner_id):
    return RecoveryShare.query.filter_by(owner_id=owner_id, status='accepted').all()


def _recovery_ready(user):
    return bool(user.shamir_wrapped_key) and len(_accepted_shares(user.id)) >= SHAMIR_THRESHOLD


def _notify(email, subject, **content):
    """Email d'information (ne contient jamais de part ni de clé)."""
    try:
        send_vault_mail(email, subject, **content)
    except Exception as e:
        app.logger.warning(f'Notification non envoyée à {email} : {e}')

@app.route('/api/recovery-contacts', methods=['GET'])
def api_recovery_contacts():
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    shares = RecoveryShare.query.filter_by(owner_id=user.id).order_by(RecoveryShare.share_index).all()
    contacts = []
    for rs in shares:
        c = User.query.get(rs.contact_id)
        if c:
            contacts.append({'username': c.username, 'email': c.email, 'status': rs.status or 'pending'})
    return jsonify({'threshold': SHAMIR_THRESHOLD, 'total': SHAMIR_SHARES,
                    'configured': bool(user.shamir_wrapped_key and shares),
                    'ready': _recovery_ready(user),
                    'configured_at': user.shamir_configured_at.strftime('%d/%m/%Y')
                    if user.shamir_configured_at else None,
                    'contacts': contacts})


@app.route('/api/recovery-contacts', methods=['POST'])
def api_recovery_contacts_setup():
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    data = request.get_json(force=True, silent=True) or {}
    contacts = data.get('contacts') or []
    if len(contacts) != SHAMIR_CONTACTS:
        return jsonify({'error': f'{SHAMIR_CONTACTS} contacts de confiance sont nécessaires.'}), 400
    ids, indexes, contact_users = set(), set(), []
    for c in contacts:
        cu = User.query.get(int(c.get('contact_id') or 0))
        if not cu or cu.id == user.id or cu.is_admin or not cu.public_key:
            return jsonify({'error': 'Contact invalide.'}), 400
        idx = int(c.get('share_index') or 0)
        if not 1 <= idx <= SHAMIR_SHARES or not c.get('encrypted_share'):
            return jsonify({'error': 'Part invalide.'}), 400
        ids.add(cu.id)
        indexes.add(idx)
        contact_users.append(cu)
    if len(ids) != SHAMIR_CONTACTS or len(indexes) != SHAMIR_CONTACTS:
        return jsonify({'error': f'Choisissez {SHAMIR_CONTACTS} contacts différents.'}), 400
    if not data.get('shamir_wrapped_key') or not data.get('shamir_auth_value'):
        return jsonify({'error': 'Données de récupération manquantes.'}), 400
    try:
        auth_hash = hash_auth_value(data['shamir_auth_value'])
    except Exception:
        return jsonify({'error': 'Valeur invalide.'}), 400
    RecoveryShare.query.filter_by(owner_id=user.id).delete()
    for c in contacts:
        db.session.add(RecoveryShare(owner_id=user.id, contact_id=int(c['contact_id']),
                                     share_index=int(c['share_index']),
                                     encrypted_share=c['encrypted_share'], status='pending'))
    user.shamir_wrapped_key = data['shamir_wrapped_key']
    user.shamir_auth_hash = auth_hash
    user.shamir_configured_at = _utcnow()
    log_activity(user.id, 'Contacts de confiance configurés')
    db.session.commit()
    for cu in contact_users:
        _notify(cu.email, f'{user.username} vous invite à être son contact de récupération - Vault',
                title='Invitation : contact de récupération',
                greeting=f'Bonjour {cu.username},',
                paragraphs=[f'{user.username} ({user.email}) souhaite vous désigner comme contact de '
                            'récupération sur Vault.',
                            f"Si vous acceptez et qu'un jour {user.username} perd l'accès à son compte, il vous "
                            f'demandera de valider sa récupération ({SHAMIR_THRESHOLD} contacts sur '
                            f'{SHAMIR_SHARES} devront valider).'],
                button=('Répondre à l\'invitation', _app_url('/trusted-contacts')),
                notice='Cet email ne contient aucune clé : votre part est chiffrée et ne peut être '
                       'utilisée que depuis votre compte Vault.')
    return jsonify({'ok': True})


@app.route('/api/recovery-invitations')
def api_recovery_invitations():
    """Invitations à devenir contact de récupération, en attente de ma réponse."""
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    out = []
    for rs in RecoveryShare.query.filter_by(contact_id=user.id, status='pending').all():
        owner = User.query.get(rs.owner_id)
        if owner:
            out.append({'id': rs.id, 'owner': owner.username, 'owner_email': owner.email,
                        'created_at': rs.created_at.strftime('%d/%m/%Y %H:%M')})
    accepted = []
    for rs in RecoveryShare.query.filter_by(contact_id=user.id, status='accepted').all():
        owner = User.query.get(rs.owner_id)
        if owner:
            accepted.append({'owner': owner.username, 'owner_email': owner.email})
    return jsonify({'invitations': out, 'accepted': accepted})


@app.route('/api/recovery-invitations/<int:share_id>/respond', methods=['POST'])
def api_recovery_invitation_respond(share_id):
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    rs = RecoveryShare.query.get(share_id)
    if not rs or rs.contact_id != user.id:
        return jsonify({'error': 'Invitation introuvable'}), 404
    data = request.get_json(force=True, silent=True) or {}
    accept = bool(data.get('accept'))
    rs.status = 'accepted' if accept else 'declined'
    rs.responded_at = _utcnow()
    log_activity(user.id, 'Contact de récupération ' + ('accepté' if accept else 'refusé'))
    db.session.commit()
    owner = User.query.get(rs.owner_id)
    if owner:
        _notify(owner.email, f"{user.username} a {'accepté' if accept else 'refusé'} votre invitation - Vault",
                title='Réponse de votre contact de récupération',
                greeting=f'Bonjour {owner.username},',
                paragraphs=[f"{user.username} ({user.email}) a {'accepté' if accept else 'refusé'} "
                            "d'être votre contact de récupération."
                            + ('' if accept else ' Choisissez un autre contact pour le remplacer.')],
                button=('Voir mes contacts', _app_url('/trusted-contacts')))
    return jsonify({'ok': True, 'status': rs.status})


@app.route('/api/recovery-contacts/remove', methods=['POST'])
def api_recovery_contacts_remove():
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    RecoveryShare.query.filter_by(owner_id=user.id).delete()
    user.shamir_wrapped_key = None
    user.shamir_auth_hash = None
    user.shamir_configured_at = None
    log_activity(user.id, 'Contacts de confiance retirés')
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/shamir-recovery/start', methods=['POST'])
@csrf.exempt
@limiter.limit("5 per hour")
def api_shamir_start():
    """Étape 1 : code envoyé par email (preuve que la demande vient du titulaire)."""
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    user = User.query.filter_by(email=email).first()
    generic = {'ok': True, 'message': 'Si ce compte a configuré des contacts de confiance, '
                                      'un code vient d\'être envoyé à son adresse email.'}
    if not user or not _recovery_ready(user):
        return jsonify(generic)
    otp = generate_otp()
    session['shamir_attempts'] = 0
    session['shamir_email'] = email
    session['shamir_otp'] = otp
    session['shamir_otp_expiry'] = int(time.time()) + 300
    try:
        send_vault_mail(
            email, f'{otp} est votre code de récupération Vault',
            title='Récupération de votre compte',
            paragraphs=['Vous avez demandé à récupérer votre compte avec l\'aide de vos contacts de '
                        'confiance. Saisissez ce code pour envoyer la demande.'],
            code=otp, code_label='Code de récupération', text_label='Votre code de récupération est',
            code_note='Valable 5 minutes · usage unique',
            notice="Si vous n'êtes pas à l'origine de cette demande, ignorez ce message : sans ce code, "
                   "aucune demande ne peut être envoyée à vos contacts.",
            preheader=f'Votre code de récupération : {otp}')
    except Exception as e:
        app.logger.error(f'Échec envoi code récupération : {e}')
        if _dev_mode():
            generic['dev_otp'] = otp
    return jsonify(generic)


@app.route('/api/shamir-recovery/verify', methods=['POST'])
@csrf.exempt
@limiter.limit("20 per hour")
def api_shamir_verify():
    """Étape 2 : code correct -> demande ouverte avec la clé publique temporaire du navigateur."""
    data = request.get_json(force=True, silent=True) or {}
    email = session.get('shamir_email')
    if not email or int(time.time()) > session.get('shamir_otp_expiry', 0):
        return jsonify({'error': 'Code expiré, recommencez.'}), 400
    if not hmac.compare_digest(str(data.get('otp_code') or ''), str(session.get('shamir_otp', ''))):
        session['shamir_attempts'] = session.get('shamir_attempts', 0) + 1
        if session['shamir_attempts'] >= 3:
            for key in ['shamir_email', 'shamir_otp', 'shamir_otp_expiry', 'shamir_attempts']:
                session.pop(key, None)
            return jsonify({'error': 'Trop de tentatives. Recommencez la demande.'}), 400
        return jsonify({'error': 'Code invalide'}), 400
    if not data.get('temp_public_key'):
        return jsonify({'error': 'Clé temporaire manquante'}), 400
    user = User.query.filter_by(email=email).first()
    if not user or not _recovery_ready(user):
        return jsonify({'error': 'Récupération indisponible pour ce compte.'}), 400
    for key in ['shamir_email', 'shamir_otp', 'shamir_otp_expiry', 'shamir_attempts']:
        session.pop(key, None)
    for old in RecoveryRequest.query.filter_by(owner_id=user.id, status='pending').all():
        old.status = 'cancelled'
    rq = RecoveryRequest(owner_id=user.id, token=secrets.token_urlsafe(32),
                         temp_public_key=data['temp_public_key'],
                         expires_at=_utcnow() + timedelta(days=2))
    db.session.add(rq)
    log_activity(user.id, 'Demande de récupération (contacts)')
    db.session.commit()
    names = []
    for rs in _accepted_shares(user.id):
        cu = User.query.get(rs.contact_id)
        if not cu:
            continue
        names.append(cu.username)
        _notify(cu.email, f'{user.username} a besoin de vous pour récupérer son compte - Vault',
                title='Demande de récupération de compte',
                greeting=f'Bonjour {cu.username},',
                paragraphs=[f'{user.username} ({user.email}) demande à récupérer son compte Vault et a '
                            'besoin de votre validation. La demande expire dans 48 heures.'],
                notice="Avant de valider, appelez-le ou voyez-le en personne pour vérifier que c'est bien "
                       "lui, et lisez-lui l'empreinte de la demande affichée dans votre compte : elle doit "
                       "être identique à celle qu'il voit sur son écran. Si ce n'est pas lui, ou si "
                       "l'empreinte est différente, ne validez pas.",
                button=('Voir la demande', _app_url('/trusted-contacts')))
    return jsonify({'ok': True, 'token': rq.token, 'contacts': names,
                    'threshold': SHAMIR_THRESHOLD})


def _active_request(token):
    rq = RecoveryRequest.query.filter_by(token=token or '').first()
    if not rq or rq.status != 'pending' or rq.expires_at < _utcnow():
        return None
    return rq


@app.route('/api/shamir-recovery/status', methods=['POST'])
@csrf.exempt
def api_shamir_status():
    data = request.get_json(force=True, silent=True) or {}
    rq = _active_request(data.get('token'))
    if not rq:
        return jsonify({'error': 'Demande introuvable ou expirée.'}), 404
    owner = User.query.get(rq.owner_id)
    approvals = [{'share_index': a.share_index, 'encrypted_share': a.encrypted_share,
                  'contact': User.query.get(a.contact_id).username}
                 for a in RecoveryApproval.query.filter_by(request_id=rq.id).all()]
    return jsonify({'email': owner.email, 'approvals': approvals, 'threshold': SHAMIR_THRESHOLD,
                    'shamir_wrapped_key': owner.shamir_wrapped_key})


@app.route('/api/shamir-recovery/complete', methods=['POST'])
@csrf.exempt
def api_shamir_complete():
    """Étape finale : preuve de possession de la clé reconstituée + nouveau coffre."""
    data = request.get_json(force=True, silent=True) or {}
    rq = _active_request(data.get('token'))
    if not rq:
        return jsonify({'error': 'Demande introuvable ou expirée.'}), 404
    user = User.query.get(rq.owner_id)
    if not user.shamir_auth_hash or not verify_auth_value(data.get('shamir_auth_value') or '',
                                                         user.shamir_auth_hash):
        return jsonify({'error': 'Clé de récupération incorrecte.'}), 401
    if not all(data.get(k) for k in ('auth_value', 'salt', 'encrypted_private_key')):
        return jsonify({'error': 'Données manquantes'}), 400
    user.auth_hash = hash_auth_value(data['auth_value'])
    user.salt = data['salt']
    user.encrypted_private_key = data['encrypted_private_key']
    user.is_temp_password = False
    rq.status = 'completed'
    log_activity(user.id, 'Compte récupéré (contacts de confiance)')
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/recovery-requests')
def api_recovery_requests_for_me():
    """Demandes de récupération où je suis contact de confiance et pas encore approuvées."""
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    out = []
    for rs in RecoveryShare.query.filter_by(contact_id=user.id, status='accepted').all():
        for rq in RecoveryRequest.query.filter_by(owner_id=rs.owner_id, status='pending').all():
            if rq.expires_at < _utcnow():
                continue
            if RecoveryApproval.query.filter_by(request_id=rq.id, contact_id=user.id).first():
                continue
            owner = User.query.get(rq.owner_id)
            out.append({'request_id': rq.id, 'owner': owner.username, 'owner_email': owner.email,
                        'created_at': rq.created_at.strftime('%d/%m/%Y %H:%M'),
                        'temp_public_key': rq.temp_public_key,
                        'share_index': rs.share_index, 'encrypted_share': rs.encrypted_share})
    return jsonify({'requests': out})


@app.route('/api/recovery-requests/<int:request_id>/approve', methods=['POST'])
def api_recovery_approve(request_id):
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    rq = RecoveryRequest.query.get(request_id)
    if not rq or rq.status != 'pending' or rq.expires_at < _utcnow():
        return jsonify({'error': 'Demande introuvable ou expirée.'}), 404
    rs = RecoveryShare.query.filter_by(owner_id=rq.owner_id, contact_id=user.id, status='accepted').first()
    if not rs:
        return jsonify({'error': "Vous n'êtes pas contact de confiance pour ce compte."}), 403
    data = request.get_json(force=True, silent=True) or {}
    if not data.get('encrypted_share'):
        return jsonify({'error': 'Part manquante'}), 400
    if not RecoveryApproval.query.filter_by(request_id=rq.id, contact_id=user.id).first():
        db.session.add(RecoveryApproval(request_id=rq.id, contact_id=user.id,
                                        share_index=rs.share_index,
                                        encrypted_share=data['encrypted_share']))
    log_activity(user.id, 'Approbation récupération')
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/trusted-contacts')
def trusted_contacts_page():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    return render_template('trusted_contacts.html', user=user, stats=_storage_stats(user))


@app.route('/recover/contacts')
def recover_contacts_page():
    return render_template('recover_contacts.html')


@app.route('/api/recovery-info', methods=['POST'])
@limiter.limit("10 per hour")
def api_recovery_info():
    """Renvoie la copie de récupération CHIFFRÉE de la clé privée.
    Seul le détenteur de la phrase BIP-39 peut la déchiffrer (128 bits d'entropie)."""
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user or not user.recovery_wrapped_key or not user.recovery_auth_hash:
        return jsonify({'error': 'Récupération impossible pour ce compte.'}), 404
    return jsonify({'ok': True, 'recovery_wrapped_key': user.recovery_wrapped_key})


@app.route('/api/recover-confirm', methods=['POST'])
@limiter.limit("10 per hour")
def api_recover_confirm():
    """Applique le nouveau coffre UNIQUEMENT si le client prouve qu'il possède la phrase
    de récupération (preuve dérivée côté client, comparée à son Argon2id)."""
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    recovery_auth_value = data.get('recovery_auth_value')
    auth_value = data.get('auth_value')
    salt = data.get('salt')
    encrypted_private_key = data.get('encrypted_private_key')
    if not all([email, recovery_auth_value, auth_value, salt, encrypted_private_key]):
        return jsonify({'error': 'Champs manquants'}), 400
    user = User.query.filter_by(email=email).first()
    if not user or not user.recovery_auth_hash or \
            not verify_auth_value(recovery_auth_value, user.recovery_auth_hash):
        app.logger.warning(f'Échec de récupération pour {email} depuis {request.remote_addr}')
        return jsonify({'error': 'Phrase de récupération incorrecte pour ce compte.'}), 403
    try:
        user.auth_hash = hash_auth_value(auth_value)
    except Exception:
        return jsonify({'error': "Valeur d'authentification invalide"}), 400
    user.salt = salt
    user.encrypted_private_key = encrypted_private_key
    user.otp_secret = ''
    user.otp_expiry = 0
    # Toutes les sessions existantes sont fermées
    ActiveSession.query.filter_by(user_id=user.id).delete()
    log_activity(user.id, 'Récupération de compte')
    db.session.commit()
    return jsonify({'ok': True})


@app.route('/api/change-password', methods=['POST'])
@limiter.limit("10 per hour")
def api_change_password():
    user = current_user()
    if not user:
        return jsonify({'error': 'Non connecté'}), 401
    data = request.get_json(force=True, silent=True) or {}
    current_auth_value = data.get('current_auth_value')
    auth_value = data.get('auth_value')
    salt = data.get('salt')
    encrypted_private_key = data.get('encrypted_private_key')
    if not all([current_auth_value, auth_value, salt, encrypted_private_key]):
        return jsonify({'error': 'Champs manquants'}), 400
    if not verify_auth_value(current_auth_value, user.auth_hash):
        return jsonify({'error': 'Mot de passe actuel incorrect.'}), 403
    try:
        user.auth_hash = hash_auth_value(auth_value)
    except Exception:
        return jsonify({'error': "Valeur d'authentification invalide"}), 400
    user.salt = salt
    user.encrypted_private_key = encrypted_private_key
    log_activity(user.id, 'Changement de mot de passe')
    db.session.commit()
    return jsonify({'ok': True})


# ══════════════════════════════════════════════════════════════
# ABONNEMENTS / CAMPAY (inchangé)
# ══════════════════════════════════════════════════════════════

@app.route('/plans')
def plans_page():
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    billing = request.args.get('billing', 'monthly')
    if billing not in ['monthly', 'yearly']:
        billing = 'monthly'
    plans_data = []
    for key, p in PLANS.items():
        dm = p.get('display_price_monthly', p['price_monthly'])
        dy = p.get('display_price_yearly', p['price_yearly'])
        dmo = dm
        if p['reduction_size'] > 0:
            dmo = int(dm / (1 - p['reduction_size'] / 100))
        plans_data.append({
            'key': key, 'name': p['name'],
            'quota': format_size(p['quota']), 'quota_bytes': p['quota'],
            'price_monthly': dm, 'price_yearly': dy,
            'price_monthly_original': dmo,
            'price_yearly_original': dm * 12,
            'duration_days_monthly': p['duration_days_monthly'],
            'duration_days_yearly': p['duration_days_yearly'],
            'description': p['description'],
            'reduction_size': p['reduction_size'],
            'reduction_yearly': p['reduction_yearly'],
            'savings_yearly': (dm * 12) - dy,
            'is_current': user.plan == key,
        })
    return render_template('plans.html', user=user, plans=plans_data, billing=billing)



CAMPAY_MIN_AMOUNT = 10

@app.route('/subscribe/<plan_key>', methods=['GET', 'POST'])
def subscribe(plan_key):
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    if plan_key not in PLANS or plan_key == 'free':
        flash('Plan invalide.', 'error')
        return redirect(url_for('plans_page'))
    plan = PLANS[plan_key]
    billing_cycle = request.args.get('billing', 'monthly')
    if billing_cycle not in ['monthly', 'yearly']:
        billing_cycle = 'monthly'

    if request.method == 'POST':
        phone = (request.form.get('phone') or '').strip()
        operator = (request.form.get('operator') or '').strip()
        billing_cycle = request.form.get('billing_cycle', billing_cycle)
        if billing_cycle not in ['monthly', 'yearly']:
            billing_cycle = 'monthly'

        phone = phone.replace(' ', '').replace('-', '')
        if not phone or len(phone) != 9 or not phone[0].isdigit():
            flash('Numéro de téléphone invalide. Format : 6XXXXXXXX', 'error')
            return redirect(url_for('subscribe', plan_key=plan_key, billing=billing_cycle))
        if operator not in ['orange', 'mtn']:
            flash('Veuillez choisir un opérateur.', 'error')
            return redirect(url_for('subscribe', plan_key=plan_key, billing=billing_cycle))

        # Deux montants : le prix affiché à l'utilisateur (display_price_*), qui est aussi
        # celui enregistré dans l'historique et les statistiques, et le montant réellement
        # demandé à CamPay (price_*), réduit pendant les tests.
        if billing_cycle == 'yearly':
            amount, charged, duration = plan['display_price_yearly'], plan['price_yearly'], 365
        else:
            amount, charged, duration = plan['display_price_monthly'], plan['price_monthly'], 30

        promo_code_str = (request.form.get('promo_code') or '').strip().upper()
        promo = None
        if promo_code_str:
            promo = PromoCode.query.filter_by(code=promo_code_str, is_active=True).first()
            if promo and (not promo.expires_at or promo.expires_at >= _utcnow()):
                if promo.max_uses == 0 or promo.uses_count < promo.max_uses:
                    if promo.applicable_plans == 'all' or plan_key in \
                            [p.strip() for p in promo.applicable_plans.split(',')]:
                        amount = max(1, int(amount * (1 - promo.discount_percent / 100)))
                        charged = max(1, int(charged * (1 - promo.discount_percent / 100)))

        # Minimum accepté par les opérateurs (Orange Money refuse moins de 10 FCFA).
        charged = max(CAMPAY_MIN_AMOUNT, int(charged))

        reference = secrets.token_urlsafe(16)
        payment = Payment(user_id=user.id, reference=reference, plan=plan_key,
                          amount=amount, status='pending',
                          operator=operator, billing_cycle=billing_cycle)
        db.session.add(payment)
        if promo:
            promo.uses_count += 1
        db.session.commit()

        campay_ref = initiate_payment(
            amount=charged, phone_number='237' + phone,
            description=f"Vault - Abonnement {plan['name']} ({billing_cycle})",
            external_reference=reference)
        if not campay_ref:
            # Le paiement n'a pas pu démarrer : on le dit tout de suite au lieu d'attendre
            payment.status = 'failed'
            db.session.commit()
            app.logger.warning(f'CamPay : paiement non lancé ({payment_module.last_error})')
            flash("Le paiement n'a pas pu être lancé : " + (payment_module.last_error or 'CamPay ne répond pas')
                  + '. Réessayez dans un instant.', 'error')
            return redirect(url_for('plans_page'))
        payment.reference = campay_ref
        db.session.commit()
        return redirect(url_for('payment_pending', payment_id=payment.id))

    if billing_cycle == 'yearly':
        amount, duration = plan['display_price_yearly'], 365
    else:
        amount, duration = plan['display_price_monthly'], 30
    return render_template('subscribe.html', user=user, plan=plan, plan_key=plan_key,
                           billing_cycle=billing_cycle, amount=amount,
                           duration_days=duration,
                           quota_display=format_size(plan['quota']))


@app.route('/payment-pending/<int:payment_id>')
def payment_pending(payment_id):
    user = current_user()
    if not user:
        return redirect(url_for('login'))
    payment = Payment.query.get(payment_id)
    if not payment or payment.user_id != user.id:
        return redirect(url_for('plans_page'))
    return render_template('payment_pending.html', user=user, payment=payment)


@app.route('/payment-check/<int:payment_id>')
def payment_check(payment_id):
    user = current_user()
    if not user:
        return jsonify({'status': 'error', 'message': 'Non connecté'})
    payment = Payment.query.get(payment_id)
    if not payment or payment.user_id != user.id:
        return jsonify({'status': 'error', 'message': 'Paiement introuvable'})
    if payment.status == 'success':
        return jsonify({'status': 'success'})
    status = check_payment_status(payment.reference)
    if status == 'SUCCESSFUL':
        _activate_payment(payment)
        db.session.commit()
        return jsonify({'status': 'success'})
    elif status == 'FAILED':
        payment.status = 'failed'
        db.session.commit()
        return jsonify({'status': 'failed'})
    return jsonify({'status': 'pending'})


def _activate_payment(payment):
    """Active l'abonnement lié à un paiement confirmé (idempotent)."""
    if payment.status == 'success':
        return
    payment.status = 'success'
    payment.confirmed_at = _utcnow()
    sub_user = User.query.get(payment.user_id)
    plan = PLANS[payment.plan]
    sub_user.plan = payment.plan
    sub_user.quota = plan['quota']
    days = 365 if payment.billing_cycle == 'yearly' else 30
    sub_user.subscription_expiry = _utcnow() + timedelta(days=days)
    sub_user.grace_period_end = None
    log_activity(sub_user.id, f'Abonnement {payment.plan} activé')


@app.route('/payment-webhook', methods=['POST'])
@csrf.exempt
@limiter.limit("60 per minute")
def payment_webhook():
    """Notification de l'agrégateur. Son contenu n'est jamais cru sur parole :
    le statut est redemandé à l'API CamPay (authentifiée) avant toute activation,
    de sorte qu'une notification forgée ne peut pas activer un abonnement."""
    data = request.get_json(silent=True)
    if not data:
        return 'OK', 200
    payment = Payment.query.filter_by(reference=data.get('reference')).first()
    if not payment or payment.status != 'pending':
        return 'OK', 200
    status = check_payment_status(payment.reference)
    if status == 'SUCCESSFUL':
        _activate_payment(payment)
    elif status == 'FAILED':
        payment.status = 'failed'
    db.session.commit()
    return 'OK', 200


@app.route('/api/check-promo', methods=['POST'])
def check_promo():
    user = current_user()
    if not user:
        return jsonify({'valid': False, 'message': 'Non connecté'})
    data = request.get_json(force=True, silent=True) or {}
    code = (data.get('code') or '').strip().upper()
    plan_key = data.get('plan', '')
    if not code:
        return jsonify({'valid': False, 'message': ''})
    promo = PromoCode.query.filter_by(code=code, is_active=True).first()
    if not promo:
        return jsonify({'valid': False, 'message': 'Code invalide ou inactif.'})
    if promo.expires_at and promo.expires_at < _utcnow():
        return jsonify({'valid': False, 'message': 'Code expiré.'})
    if promo.max_uses > 0 and promo.uses_count >= promo.max_uses:
        return jsonify({'valid': False, 'message': 'Code épuisé.'})
    if promo.applicable_plans != 'all':
        if plan_key not in [p.strip() for p in promo.applicable_plans.split(',')]:
            return jsonify({'valid': False,
                            'message': f'Code non applicable au plan {plan_key}.'})
    return jsonify({'valid': True, 'discount': promo.discount_percent,
                    'message': f'{promo.discount_percent}% de réduction appliquée !'})


@app.route('/logout')
def logout():
    token = session.get('session_token')
    if token:
        active = ActiveSession.query.filter_by(session_token=token).first()
        if active:
            db.session.delete(active)
            db.session.commit()
    saved_lang = session.get('language')
    session.clear()
    if saved_lang:
        session['language'] = saved_lang
    resp = redirect(url_for('login'))
    # Le navigateur efface aussi son stockage local (dont la clé privée dans IndexedDB),
    # même si la déconnexion part d'une page qui ne charge pas vault-keystore.js.
    resp.headers['Clear-Site-Data'] = '"storage"'
    return resp


# ══════════════════════════════════════════════════════════════
# ADMIN (sans clé privée : le back-office voit des octets aveugles)
# ══════════════════════════════════════════════════════════════

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        user = current_user()
        if not user or not session.get('admin_authenticated'):
            return redirect(url_for('admin_login'))
        if not user.is_admin:
            flash('Accès refusé.', 'error')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/admin/get-salt', methods=['POST'])
@csrf.exempt
def admin_get_salt():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    user = User.query.filter_by(email=email, is_admin=True).first()
    if user:
        return jsonify({'salt': user.salt, 'iterations': PBKDF2_ITERATIONS})
    return jsonify({'salt': fake_salt_for('no-admin', email), 'iterations': PBKDF2_ITERATIONS})


@app.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=['POST'])
def admin_login():
    if request.method == 'POST':
        data = request.get_json(force=True, silent=True) or {}
        email = (data.get('email') or '').strip().lower()
        auth_value_hex = data.get('auth_value')
        user = User.query.filter_by(email=email, is_admin=True).first()
        if user is None or not verify_auth_value(auth_value_hex or '', user.auth_hash):
            return jsonify({'error': 'Identifiants administrateur incorrects.'}), 401

        session['user_id'] = user.id
        session['last_activity'] = int(time.time())
        session['admin_authenticated'] = True
        if session.get('language') in ('fr', 'en'):   # langue choisie sur la page de connexion
            user.language = session['language']
        token = secrets.token_urlsafe(32)
        db.session.add(ActiveSession(user_id=user.id, session_token=token,
                                     ip_address=request.remote_addr,
                                     user_agent=(request.headers.get('User-Agent') or '')[:200]))
        log_activity(user.id, 'Connexion admin')
        db.session.commit()
        session['session_token'] = token
        return jsonify({'ok': True, 'redirect': url_for('admin_dashboard')})
    return render_template('admin_login.html')


@app.route('/admin')
@admin_required
def admin_dashboard():
    total_users = User.query.filter_by(is_admin=False).count()
    total_files = FileMetadata.query.filter_by(is_deleted=False).count()
    total_storage = db.session.query(
        db.func.coalesce(db.func.sum(FileMetadata.stored_size), 0)) \
        .filter_by(is_deleted=False).scalar() or 0
    total_payments = Payment.query.filter_by(status='success').count()
    total_revenue = db.session.query(
        db.func.coalesce(db.func.sum(Payment.amount), 0)) \
        .filter_by(status='success').scalar() or 0
    plan_stats = {k: User.query.filter_by(plan=k, is_admin=False).count() for k in PLANS.keys()}
    recent_users = User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).limit(8).all()
    recent_payments = []
    for p in Payment.query.order_by(Payment.created_at.desc()).limit(8).all():
        u = User.query.get(p.user_id)
        recent_payments.append({'email': u.email if u else '—', 'plan': p.plan, 'amount': p.amount,
                                'status': p.status, 'operator': p.operator or '—',
                                'created_at': p.created_at.strftime('%d/%m/%Y') if p.created_at else '—'})
    recent_activity = []
    for log in ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(12).all():
        u = User.query.get(log.user_id)
        # Aucun nom de fichier côté serveur : seul l'identifiant opaque est affiché
        recent_activity.append({'username': u.username if u else 'Système', 'action': log.action,
                                'filename': (log.file_uuid or '')[:8], 'timestamp': log.timestamp})
    return render_template('admin.html', admin=current_user(),
                           total_users=total_users, total_files=total_files,
                           total_storage=format_size(total_storage),
                           total_payments=total_payments, total_revenue=total_revenue,
                           pending_payments_count=Payment.query.filter_by(status='pending').count(),
                           plan_stats=plan_stats,
                           active_sessions_count=ActiveSession.query.count(),
                           recent_users=recent_users, recent_payments=recent_payments,
                           recent_activity=recent_activity)


@app.route('/admin/users')
@admin_required
def admin_users():
    search = request.args.get('q', '').strip()
    query = User.query.filter_by(is_admin=False)
    if search:
        query = query.filter(db.or_(User.email.ilike(f'%{search}%'),
                                    User.username.ilike(f'%{search}%')))
    plan_filter = request.args.get('plan', '')
    status_filter = request.args.get('status', '')
    if plan_filter:
        query = query.filter_by(plan=plan_filter)
    users = []
    for u in query.order_by(User.created_at.desc()).all():
        if status_filter == 'active' and u.is_suspended:
            continue
        if status_filter == 'suspended' and not u.is_suspended:
            continue
        used = db.session.query(db.func.coalesce(db.func.sum(FileMetadata.stored_size), 0)) \
            .filter_by(user_id=u.id, is_deleted=False).scalar() or 0
        u.used = format_size(used)
        u.used_percent = min(round((used / u.quota) * 100, 1), 100) if u.quota > 0 else 0
        u.file_count = FileMetadata.query.filter_by(user_id=u.id, is_deleted=False).count()
        users.append(u)
    return render_template('admin_users.html', admin=current_user(), users=users,
                           search=search, plan_filter=plan_filter, status_filter=status_filter)


@app.route('/admin/user/<int:user_id>')
@admin_required
def admin_user_detail(user_id):
    user = User.query.get_or_404(user_id)
    used = db.session.query(db.func.coalesce(db.func.sum(FileMetadata.stored_size), 0)) \
        .filter_by(user_id=user.id, is_deleted=False).scalar() or 0
    files = FileMetadata.query.filter_by(user_id=user.id, is_deleted=False) \
        .order_by(FileMetadata.uploaded_at.desc()).limit(20).all()
    payments = Payment.query.filter_by(user_id=user.id) \
        .order_by(Payment.created_at.desc()).all()
    sessions_list = ActiveSession.query.filter_by(user_id=user.id).all()
    activity = ActivityLog.query.filter_by(user_id=user.id) \
        .order_by(ActivityLog.timestamp.desc()).limit(20).all()
    return render_template('admin_user_detail.html',
                           admin=current_user(), user=user,
                           used_space=format_size(used),
                           total_quota=format_size(user.quota),
                           used_percent=min(round((used / user.quota) * 100, 1), 100) if user.quota > 0 else 0,
                           files=files, payments=payments,
                           sessions=sessions_list, activity=activity,
                           format_size=format_size)


@app.route('/admin/user/<int:user_id>/change-plan', methods=['POST'])
@admin_required
def admin_change_plan(user_id):
    u = User.query.get_or_404(user_id)
    new_plan = request.form.get('new_plan', 'free')
    if new_plan not in PLANS:
        flash('Plan invalide.', 'error')
        return redirect(url_for('admin_user_detail', user_id=user_id))
    u.plan = new_plan
    u.quota = PLANS[new_plan]['quota']
    u.subscription_expiry = None if new_plan == 'free' else _utcnow() + timedelta(days=30)
    db.session.commit()
    flash(f'Plan de {u.email} changé en {new_plan}.', 'success')
    return redirect(url_for('admin_user_detail', user_id=user_id))


@app.route('/admin/user/<int:user_id>/suspend', methods=['POST'])
@admin_required
def admin_suspend_user(user_id):
    u = User.query.get_or_404(user_id)
    if not u.is_admin:
        u.is_suspended = True
        db.session.commit()
    return redirect(request.referrer or url_for('admin_users'))


@app.route('/admin/user/<int:user_id>/activate', methods=['POST'])
@admin_required
def admin_activate_user(user_id):
    u = User.query.get_or_404(user_id)
    if not u.is_admin:
        u.is_suspended = False
        db.session.commit()
    return redirect(request.referrer or url_for('admin_users'))


@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if not user.is_admin:
        for f in FileMetadata.query.filter_by(user_id=user.id).all():
            path = os.path.join(app.config['UPLOAD_FOLDER'], f.stored_filename)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        for f in FileMetadata.query.filter_by(user_id=user.id).all():
            _purge_file_relations(f)
        for d in Delegation.query.filter((Delegation.owner_id == user.id) |
                                         (Delegation.recipient_id == user.id)).all():
            FileShare.query.filter_by(delegation_id=d.id).delete()
            db.session.delete(d)
        RecoveryShare.query.filter((RecoveryShare.owner_id == user.id) |
                                   (RecoveryShare.contact_id == user.id)).delete()
        for rq in RecoveryRequest.query.filter_by(owner_id=user.id).all():
            RecoveryApproval.query.filter_by(request_id=rq.id).delete()
            db.session.delete(rq)
        RecoveryApproval.query.filter_by(contact_id=user.id).delete()
        FileMetadata.query.filter_by(user_id=user.id).delete()
        ActivityLog.query.filter_by(user_id=user.id).delete()
        ActiveSession.query.filter_by(user_id=user.id).delete()
        Payment.query.filter_by(user_id=user.id).delete()
        DownloadTicket.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
    return redirect(url_for('admin_users'))


@app.route('/admin/payments')
@admin_required
def admin_payments():
    payments = Payment.query.order_by(Payment.created_at.desc()).all()
    total_revenue = db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)) \
        .filter_by(status='success').scalar() or 0
    return render_template('admin_payments.html', admin=current_user(),
                           payments=payments, total_revenue=total_revenue)


@app.route('/admin/activity')
@admin_required
def admin_activity():
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(200).all()
    return render_template('admin_activity.html', admin=current_user(), logs=logs)


@app.route('/admin/api/stats')
@admin_required
def admin_api_stats():
    """Données des graphiques du tableau de bord administrateur."""
    signups_by_month, labels_months, revenue_by_month = [], [], []
    for i in range(5, -1, -1):
        d = _utcnow() - timedelta(days=30 * i)
        month_start = d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        month_end = (month_start + timedelta(days=32)).replace(day=1) if i > 0 else _utcnow()
        signups_by_month.append(User.query.filter(
            User.created_at >= month_start, User.created_at < month_end,
            User.is_admin == False).count())  # noqa: E712
        labels_months.append(d.strftime('%b %Y'))
        total = db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.status == 'success', Payment.confirmed_at >= month_start,
            Payment.confirmed_at < month_end).scalar() or 0
        revenue_by_month.append(int(total))
    plan_data = {k: User.query.filter_by(plan=k, is_admin=False).count() for k in PLANS.keys()}
    return jsonify({'labels_months': labels_months, 'signups_by_month': signups_by_month,
                    'revenue_by_month': revenue_by_month, 'plan_data': plan_data,
                    'active_now': ActiveSession.query.count()})


def _csv_response(rows, header, filename):
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)
    writer.writerow(header)
    writer.writerows(rows)
    return Response('\ufeff' + output.getvalue(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename={filename}'})


@app.route('/admin/export/users')
@admin_required
def admin_export_users():
    rows = []
    for u in User.query.filter_by(is_admin=False).order_by(User.created_at.desc()).all():
        used = db.session.query(db.func.coalesce(db.func.sum(FileMetadata.stored_size), 0)) \
            .filter_by(user_id=u.id, is_deleted=False).scalar() or 0
        rows.append([u.id, u.username, u.email, u.plan, round(u.quota / (1024 ** 3), 1),
                     round(used / (1024 ** 2), 2),
                     FileMetadata.query.filter_by(user_id=u.id, is_deleted=False).count(),
                     u.created_at.strftime('%d/%m/%Y') if u.created_at else '',
                     u.subscription_expiry.strftime('%d/%m/%Y') if u.subscription_expiry else '',
                     'Oui' if u.is_suspended else 'Non'])
    return _csv_response(rows, ['ID', 'Username', 'Email', 'Plan', 'Quota (Go)',
                                'Espace utilisé (Mo)', 'Fichiers', 'Inscrit le',
                                'Abonnement expire le', 'Suspendu'], 'vault_utilisateurs.csv')


@app.route('/admin/export/payments')
@admin_required
def admin_export_payments():
    rows = []
    for p in Payment.query.order_by(Payment.created_at.desc()).all():
        u = User.query.get(p.user_id)
        rows.append([p.id, u.email if u else '', u.username if u else '', p.plan, p.amount,
                     'Annuel' if p.billing_cycle == 'yearly' else 'Mensuel', p.operator or '',
                     p.status, p.created_at.strftime('%d/%m/%Y %H:%M') if p.created_at else '',
                     p.confirmed_at.strftime('%d/%m/%Y %H:%M') if p.confirmed_at else ''])
    return _csv_response(rows, ['ID', 'Email utilisateur', 'Username', 'Plan', 'Montant (FCFA)',
                                'Cycle', 'Opérateur', 'Statut', 'Créé le', 'Confirmé le'],
                         'vault_paiements.csv')


@app.route('/admin/promos')
@admin_required
def admin_promos():
    promos = PromoCode.query.order_by(PromoCode.created_at.desc()).all()
    return render_template('admin_promos.html', admin=current_user(), promos=promos,
                           plans=PLANS, now=_utcnow())


@app.route('/admin/promos/create', methods=['POST'])
@admin_required
def admin_create_promo():
    code = (request.form.get('code') or '').strip().upper()
    discount = (request.form.get('discount_percent') or '').strip()
    applicable = request.form.get('applicable_plans', 'all')
    max_uses = (request.form.get('max_uses') or '0').strip()
    expires_at_str = (request.form.get('expires_at') or '').strip()
    description = (request.form.get('description') or '').strip()
    if not code or not discount:
        flash('Code et réduction obligatoires.', 'error')
        return redirect(url_for('admin_promos'))
    if PromoCode.query.filter_by(code=code).first():
        flash(f'Le code "{code}" existe déjà.', 'error')
        return redirect(url_for('admin_promos'))
    try:
        discount_int = int(discount)
        if not 1 <= discount_int <= 100:
            raise ValueError
    except ValueError:
        flash('La réduction doit être un entier entre 1 et 100.', 'error')
        return redirect(url_for('admin_promos'))
    expires_at = None
    if expires_at_str:
        try:
            expires_at = datetime.strptime(expires_at_str, '%Y-%m-%d')
        except ValueError:
            flash('Format de date invalide.', 'error')
            return redirect(url_for('admin_promos'))
    db.session.add(PromoCode(code=code, discount_percent=discount_int,
                             applicable_plans=applicable,
                             max_uses=int(max_uses) if max_uses.isdigit() else 0,
                             expires_at=expires_at, description=description))
    db.session.commit()
    flash(f'Code promo "{code}" créé avec succès.', 'success')
    return redirect(url_for('admin_promos'))


@app.route('/admin/promos/<int:promo_id>/toggle', methods=['POST'])
@admin_required
def admin_toggle_promo(promo_id):
    promo = PromoCode.query.get_or_404(promo_id)
    promo.is_active = not promo.is_active
    db.session.commit()
    flash(f'Code "{promo.code}" {"activé" if promo.is_active else "désactivé"}.', 'success')
    return redirect(url_for('admin_promos'))


@app.route('/admin/promos/<int:promo_id>/delete', methods=['POST'])
@admin_required
def admin_delete_promo(promo_id):
    promo = PromoCode.query.get_or_404(promo_id)
    code = promo.code
    db.session.delete(promo)
    db.session.commit()
    flash(f'Code "{code}" supprimé.', 'success')
    return redirect(url_for('admin_promos'))


if __name__ == '__main__':
    import socket

    def _port_free(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sk:
            try:
                sk.bind(('0.0.0.0', port))
                return True
            except OSError:
                return False

    # Port 80 (port standard du web) : l'adresse devient http://vault.localhost/
    # sans « :5000 ». S'il est déjà pris par un autre programme, Vault reprend 5000.
    port = int(os.environ.get('VAULT_PORT', 80))
    if not _port_free(port):
        print(f"[!] Le port {port} est déjà utilisé : Vault démarre sur le port 5000.")
        port = 5000
    adresse = 'http://vault.localhost' + ('' if port == 80 else f':{port}')
    print("[✓] Vault démarré en mode zero-knowledge")
    print(f"[✓] Accédez à {adresse}")
    try:
        from waitress import serve
        serve(app, host='0.0.0.0', port=port, threads=8,
              channel_timeout=1800, max_request_body_size=10 * 1024**3)
    except ImportError:
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
