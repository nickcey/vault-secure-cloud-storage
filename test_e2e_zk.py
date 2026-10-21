"""
test_e2e_zk.py — Tests de bout en bout du mode zero-knowledge de Vault.

Le test simule un navigateur honnête (mêmes primitives que vault-crypto.js,
reproduites en Python) et travaille sur une base et un dossier TEMPORAIRES :
la vraie base database/cloud.db n'est jamais touchée.

Vérifications :
 1. Inscription -> connexion (2FA) -> dépôt -> liste -> téléchargement -> renommage.
 2. Un fichier modifié sur le serveur est refusé (serveur : 409 ; client : tag AES-GCM).
 3. Partage : la clé reste dans le fragment (#), le destinataire déchiffre.
 4. Récupération : refusée sans la bonne phrase, acceptée avec ; connexion avec le nouveau mot de passe.
 5. Changement de mot de passe : refusé sans le mot de passe actuel, accepté avec.
 6. Aucune clé privée, aucun nom de fichier, aucun mot de passe en clair dans la base,
    dans le dossier de stockage ou dans la session.
 7. Toutes les pages s'affichent sans erreur serveur.

Usage :  venv\\Scripts\\python test_e2e_zk.py
"""

import base64
import hashlib
import json
import os
import secrets
import shutil
import sys
import tempfile

# ── Environnement isolé AVANT d'importer l'application ──
_TMP = tempfile.mkdtemp(prefix='vault_test_')
os.environ['VAULT_DB_PATH'] = os.path.join(_TMP, 'test.db')
os.environ['VAULT_UPLOAD_FOLDER'] = os.path.join(_TMP, 'uploads')
os.environ.setdefault('FLASK_ENV', 'development')
os.environ['VAULT_DEV_SHOW_CODES'] = '1'   # tests : le serveur de courriel est absent, le code est lu à l'écran
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cryptography.hazmat.primitives import hashes, serialization                       # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa, padding as rsa_padding      # noqa: E402
from cryptography.hazmat.primitives.ciphers.aead import AESGCM                         # noqa: E402
from cryptography.hazmat.primitives.kdf.hkdf import HKDF                               # noqa: E402
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC                       # noqa: E402
from mnemonic import Mnemonic                                                          # noqa: E402

from app import app, PBKDF2_ITERATIONS                                                  # noqa: E402
from database.models import db, User, FileMetadata                                      # noqa: E402

app.config['WTF_CSRF_ENABLED'] = False      # le jeton CSRF est testé par le navigateur
app.config['RATELIMIT_ENABLED'] = False
try:
    from app import limiter
    limiter.enabled = False
except Exception:
    pass

EMAIL = f'test_{secrets.token_hex(4)}@example.com'
PASSWORD = 'MotDePasse-Test-123'
FILENAME = 'releve_bancaire_confidentiel.pdf'
CONTENT = b'CONTENU SECRET QUI NE DOIT JAMAIS FUIR ' + secrets.token_bytes(5000)

client = app.test_client()
state = {}
results = []


def check(cond, label):
    results.append((bool(cond), label))
    print(('[OK]   ' if cond else '[ÉCHEC] ') + label)
    return cond


# ── Primitives identiques à vault-crypto.js ──

def pbkdf2_512(secret: bytes, salt: bytes):
    raw = PBKDF2HMAC(algorithm=hashes.SHA256(), length=64, salt=salt,
                     iterations=PBKDF2_ITERATIONS).derive(secret)
    return raw[:32], raw[32:]


def aes_wrap_json(key: bytes, data: bytes) -> str:
    iv = secrets.token_bytes(12)
    return json.dumps({'iv': iv.hex(), 'ct': base64.b64encode(AESGCM(key).encrypt(iv, data, None)).decode()})


def aes_unwrap_json(key: bytes, payload: str) -> bytes:
    p = json.loads(payload)
    return AESGCM(key).decrypt(bytes.fromhex(p['iv']), base64.b64decode(p['ct']), None)


def meta_key(file_key: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=b'', info=b'vault-metadata-v1').derive(file_key)


OAEP = rsa_padding.OAEP(mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(), label=None)

PAD_SIZES = [4 * 1024, 16 * 1024, 64 * 1024, 256 * 1024, 1024 * 1024, 4 * 1024 * 1024,
             16 * 1024 * 1024, 64 * 1024 * 1024, 256 * 1024 * 1024, 1024 * 1024 * 1024]


def padded_size(n):
    # Même règle que vaultGetPaddedSize() (Padmé, plancher 4 Kio)
    from modules.padding import get_padded_size
    return get_padded_size(n)


def post(url, payload=None, **kw):
    r = client.post(url, json=payload, **kw) if payload is not None else client.post(url, **kw)
    try:
        return r, r.get_json() or {}
    except Exception:
        return r, {}


def otp_for(email):
    with app.app_context():
        return User.query.filter_by(email=email).first().otp_secret


# ── Scénario ──

def signup():
    r = client.post('/signup', data={'username': 'Utilisateur Test', 'email': EMAIL})
    check(r.status_code == 302 and '/verify-signup-otp' in r.headers.get('Location', ''),
          'Inscription : code de vérification émis')
    with client.session_transaction() as s:
        otp = s.get('signup_otp')
        flashes = s.get('_flashes', [])
    r = client.post('/verify-signup-otp', data={'otp_code': otp})
    check(r.status_code == 302 and '/change-password' in r.headers.get('Location', ''),
          'Inscription : code vérifié, compte créé avec mot de passe temporaire')
    with client.session_transaction() as s:
        msgs = [m for _, m in s.get('_flashes', [])]
    temp_pw = next((m.split(': ', 1)[1] for m in msgs if 'Mot de passe temporaire' in m), None)
    with app.app_context():
        u = User.query.filter_by(email=EMAIL).first()
        check(u and u.is_temp_password and not u.public_key and temp_pw and temp_pw not in (u.auth_hash or ''),
              'Inscription : aucune clé créée avec le mot de passe temporaire')
    # Tant que le mot de passe n'est pas choisi, le reste est bloqué
    r = client.get('/dashboard')
    check(r.status_code == 302 and '/change-password' in r.headers.get('Location', ''),
          'Mot de passe temporaire : redirection obligatoire vers le changement')

    # Le navigateur crée les clés avec le mot de passe CHOISI
    r, b = post('/get-salt', {'email': EMAIL})
    _, temp_auth = pbkdf2_512(temp_pw.encode(), bytes.fromhex(b['salt']))
    salt = secrets.token_bytes(16)
    account_key, auth_value = pbkdf2_512(PASSWORD.encode(), salt)
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pkcs8 = priv.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                               serialization.NoEncryption())
    spki = priv.public_key().public_bytes(serialization.Encoding.DER,
                                          serialization.PublicFormat.SubjectPublicKeyInfo)
    mnemonic = Mnemonic('english').generate(strength=128)
    rec_key, rec_auth = pbkdf2_512(mnemonic.encode(), b'vault-recovery:' + EMAIL.encode())
    payload = {
        'auth_value': auth_value.hex(), 'recovery_auth_value': rec_auth.hex(),
        'salt': salt.hex(), 'public_key': base64.b64encode(spki).decode(),
        'encrypted_private_key': aes_wrap_json(account_key, pkcs8),
        'recovery_wrapped_key': aes_wrap_json(rec_key, pkcs8),
    }
    r, b = post('/api/setup-keys', dict(payload, current_auth_value='00' * 32))
    check(r.status_code == 401, 'Premier mot de passe : refusé sans le mot de passe temporaire')
    r, b = post('/api/setup-keys', dict(payload, current_auth_value=temp_auth.hex()))
    check(r.status_code == 200 and b.get('ok'), 'Premier mot de passe : coffre chiffré enregistré')
    state.update(mnemonic=mnemonic, priv=priv, pkcs8=pkcs8, password=PASSWORD)


def login(password, expect_ok=True):
    client.get('/logout')
    r, b = post('/get-salt', {'email': EMAIL})
    account_key, auth_value = pbkdf2_512(password.encode(), bytes.fromhex(b['salt']))
    r, b = post('/login', {'email': EMAIL, 'auth_value': auth_value.hex()})
    if not expect_ok:
        return r.status_code == 401
    if not b.get('ok'):
        return False
    r, b = post('/verify-otp', {'otp_code': otp_for(EMAIL)})
    if not b.get('ok'):
        return False
    pkcs8 = aes_unwrap_json(account_key, b['encrypted_private_key'])
    return pkcs8 == state['pkcs8']


def upload():
    r = client.get('/api/me')
    me = r.get_json()
    check(r.status_code == 200 and me.get('public_key'), '/api/me renvoie la clé publique')
    pub = serialization.load_der_public_key(base64.b64decode(me['public_key']))

    file_key = secrets.token_bytes(32)
    target = padded_size(len(CONTENT) + 16)
    padded = CONTENT + secrets.token_bytes(target - 16 - len(CONTENT))
    iv = secrets.token_bytes(12)
    blob = iv + AESGCM(file_key).encrypt(iv, padded, None)
    meta = json.dumps({'filename': FILENAME, 'mime_type': 'application/pdf',
                       'plaintext_size': len(CONTENT), 'padded_size': target,
                       'content_sha256': hashlib.sha256(CONTENT).hexdigest()}).encode()
    miv = secrets.token_bytes(12)
    enc_meta = base64.b64encode(miv + AESGCM(meta_key(file_key)).encrypt(miv, meta, None)).decode()
    import io
    r = client.post('/upload', data={
        'file': (io.BytesIO(blob), 'payload.enc'),
        'uuid': secrets.token_hex(16), 'aes_iv': iv.hex(),
        'encrypted_file_key': base64.b64encode(pub.encrypt(file_key, OAEP)).decode(),
        'encrypted_metadata': enc_meta,
        'metadata_sha256': hashlib.sha256(blob).hexdigest(),
        'original_size': len(CONTENT),   # ancien champ : doit être ignoré par le serveur
        'padded_size': len(blob),
    }, content_type='multipart/form-data')
    b = r.get_json() or {}
    check(r.status_code == 200 and b.get('ok'), 'Dépôt : blob chiffré accepté')
    state.update(file_key=file_key, file_id=b.get('file_id'), uuid=b.get('uuid'))


def list_and_download():
    r = client.get('/api/files')
    files = r.get_json()['files']
    f = [x for x in files if x['id'] == state['file_id']][0]
    fk = state['priv'].decrypt(base64.b64decode(f['encrypted_file_key']), OAEP)
    raw = base64.b64decode(f['encrypted_metadata'])
    meta = json.loads(AESGCM(meta_key(fk)).decrypt(raw[:12], raw[12:], None))
    check(meta['filename'] == FILENAME, 'Liste : le nom se déchiffre côté client')

    r, b = post(f"/api/download/create/{f['id']}")
    r = client.get(f"/api/download-file/{b['token']}")
    blob = r.get_data()
    plain = AESGCM(fk).decrypt(blob[:12], blob[12:], None)[:meta['plaintext_size']]
    check(r.status_code == 200 and plain == CONTENT, 'Téléchargement : contenu identique après déchiffrement')
    r2 = client.get(f"/api/download-file/{b['token']}")
    check(r2.status_code == 403, 'Téléchargement : le ticket est à usage unique')

    # Renommage (métadonnées rechiffrées par le client)
    miv = secrets.token_bytes(12)
    new_meta = dict(meta, filename='renomme.pdf')
    enc = base64.b64encode(miv + AESGCM(meta_key(fk)).encrypt(miv, json.dumps(new_meta).encode(), None)).decode()
    r, b = post(f"/api/files/{f['id']}/rename", {'encrypted_metadata': enc})
    check(b.get('ok'), 'Renommage : nouvelles métadonnées chiffrées acceptées')


def integrity():
    with app.app_context():
        f = FileMetadata.query.get(state['file_id'])
        path = os.path.join(app.config['UPLOAD_FOLDER'], f.stored_filename)
    orig = open(path, 'rb').read()
    tampered = orig[:-1] + bytes([orig[-1] ^ 0xFF])
    open(path, 'wb').write(tampered)
    try:
        r, b = post(f"/api/download/create/{state['file_id']}")
        r = client.get(f"/api/download-file/{b['token']}")
        check(r.status_code == 409, 'Intégrité : le serveur refuse un fichier modifié')
        try:
            AESGCM(state['file_key']).decrypt(tampered[:12], tampered[12:], None)
            rejected = False
        except Exception:
            rejected = True
        check(rejected, 'Intégrité : le navigateur rejette aussi un fichier modifié (tag AES-GCM)')
    finally:
        open(path, 'wb').write(orig)


def share():
    r, b = post(f"/api/share/create/{state['file_id']}", {'expiry_hours': 24, 'max_downloads': 2})
    token = b.get('token')
    check(token and '#' not in b.get('url_base', ''), 'Partage : lien créé sans clé côté serveur')
    anon = app.test_client()
    info = anon.get(f'/api/share/{token}/info').get_json()
    raw = base64.b64decode(info['encrypted_meta_b64'])
    meta = json.loads(AESGCM(meta_key(state['file_key'])).decrypt(raw[:12], raw[12:], None))
    blob = anon.get(f'/api/share/{token}/blob').get_data()
    plain = AESGCM(state['file_key']).decrypt(blob[:12], blob[12:], None)[:meta['plaintext_size']]
    check(plain == CONTENT, 'Partage : le destinataire déchiffre avec la clé du fragment')
    check(anon.get('/api/share/inexistant/info').status_code == 404,
          'Partage : un lien invalide renvoie une erreur propre (404)')


FOLDER_NAME = 'Dossier_Medical_Confidentiel'


def folders():
    """Dossiers : index chiffré côté client (même format que vault-folders.js)."""
    r, b = client.get('/api/folder-index'), None
    b = r.get_json() or {}
    check(r.status_code == 200 and not b.get('index') and b.get('version') == 0,
          'Dossiers : aucun index au départ')
    me = client.get('/api/me').get_json()
    pub = serialization.load_der_public_key(base64.b64decode(me['public_key']))
    ikey = secrets.token_bytes(32)
    index = {'v': 1, 'folders': {'f1': {'name': FOLDER_NAME, 'parent': None, 'created': '2026-10-18T10:00:00Z'}},
             'files': {state['uuid']: 'f1'}, 'shares': {}}
    js = json.dumps(index)
    js += ' ' * ((4096 - len(js) % 4096) % 4096)
    blob = aes_wrap_json(ikey, js.encode())
    wrapped = base64.b64encode(pub.encrypt(ikey, OAEP)).decode()
    r, b = post('/api/folder-index', {'index': blob, 'version': 0})
    check(r.status_code == 400, 'Dossiers : premier enregistrement refusé sans clé d\'index')
    r, b = post('/api/folder-index', {'index': 'pas du json', 'key': wrapped, 'version': 0})
    check(r.status_code == 400, 'Dossiers : index non chiffré refusé')
    r, b = post('/api/folder-index', {'index': blob, 'key': wrapped, 'version': 0})
    check(b.get('ok') and b.get('version') == 1, 'Dossiers : index chiffré enregistré')
    r, b = post('/api/folder-index', {'index': blob, 'version': 0})
    check(r.status_code == 409, 'Dossiers : écriture concurrente détectée (version périmée refusée)')
    state['folder_blob_len'] = len(blob)


def folders_readable():
    b = client.get('/api/folder-index').get_json() or {}
    ikey = state['priv'].decrypt(base64.b64decode(b['key']), OAEP)
    idx = json.loads(aes_unwrap_json(ikey, b['index']))
    check(idx['folders']['f1']['name'] == FOLDER_NAME and idx['files'].get(state['uuid']) == 'f1',
          'Dossiers : arborescence relue après changement de mot de passe')


def recovery():
    client.get('/logout')
    new_pw = 'Nouveau-MotDePasse-456'
    r, b = post('/api/recovery-info', {'email': EMAIL})
    rec_key, rec_auth = pbkdf2_512(state['mnemonic'].encode(), b'vault-recovery:' + EMAIL.encode())
    pkcs8 = aes_unwrap_json(rec_key, b['recovery_wrapped_key'])
    check(pkcs8 == state['pkcs8'], 'Récupération : la phrase déchiffre la copie de récupération')

    salt = secrets.token_bytes(16)
    nk, nauth = pbkdf2_512(new_pw.encode(), salt)
    payload = {'email': EMAIL, 'auth_value': nauth.hex(), 'salt': salt.hex(),
               'encrypted_private_key': aes_wrap_json(nk, pkcs8)}
    r, b = post('/api/recover-confirm', dict(payload, recovery_auth_value=secrets.token_hex(32)))
    check(r.status_code == 403, 'Récupération : refusée sans la bonne phrase (pas de prise de contrôle)')
    r, b = post('/api/recover-confirm', dict(payload, recovery_auth_value=rec_auth.hex()))
    check(b.get('ok'), 'Récupération : acceptée avec la bonne phrase')
    check(login(new_pw), 'Récupération : connexion avec le nouveau mot de passe')
    check(login(PASSWORD, expect_ok=False), "Récupération : l'ancien mot de passe ne fonctionne plus")
    state['password'] = new_pw


def change_password():
    assert login(state['password'])
    r, b = post('/get-salt', {'email': EMAIL})
    _, cur_auth = pbkdf2_512(state['password'].encode(), bytes.fromhex(b['salt']))
    new_pw = 'Encore-Un-Autre-789'
    salt = secrets.token_bytes(16)
    nk, nauth = pbkdf2_512(new_pw.encode(), salt)
    payload = {'auth_value': nauth.hex(), 'salt': salt.hex(),
               'encrypted_private_key': aes_wrap_json(nk, state['pkcs8'])}
    r, b = post('/api/change-password', dict(payload, current_auth_value=secrets.token_hex(32)))
    check(r.status_code == 403, 'Mot de passe : changement refusé sans le mot de passe actuel')
    r, b = post('/api/change-password', dict(payload, current_auth_value=cur_auth.hex()))
    check(b.get('ok'), 'Mot de passe : changement accepté avec le mot de passe actuel')
    check(login(new_pw), 'Mot de passe : connexion avec le nouveau mot de passe')
    state['password'] = new_pw


def no_plaintext():
    db_bytes = open(os.environ['VAULT_DB_PATH'], 'rb').read()
    pkcs8_der = state['pkcs8']
    check(b'BEGIN PRIVATE KEY' not in db_bytes and pkcs8_der[:64] not in db_bytes,
          'Base : aucune clé privée en clair')
    check(FILENAME.encode() not in db_bytes and b'renomme.pdf' not in db_bytes,
          'Base : aucun nom de fichier en clair')
    check(FOLDER_NAME.encode() not in db_bytes, 'Base : aucun nom de dossier en clair')
    check(b'CONTENU SECRET' not in db_bytes, 'Base : aucun contenu de fichier en clair')
    check(hashlib.sha256(CONTENT).hexdigest().encode() not in db_bytes,
          'Base : aucune empreinte du contenu en clair (fichier non reconnaissable)')
    with app.app_context():
        sizes = [f.original_size for f in FileMetadata.query.all()]
    check(sizes and all(v == 0 for v in sizes),
          'Base : taille réelle des fichiers absente (seule la taille après remplissage est connue)')
    check(PASSWORD.encode() not in db_bytes and state['password'].encode() not in db_bytes,
          'Base : aucun mot de passe en clair')
    check(state['mnemonic'].encode() not in db_bytes, 'Base : aucune phrase de récupération en clair')
    leaked = False
    for root, _, files in os.walk(os.environ['VAULT_UPLOAD_FOLDER']):
        for name in files:
            data = open(os.path.join(root, name), 'rb').read()
            if b'CONTENU SECRET' in data or FILENAME.encode() in data:
                leaked = True
    check(not leaked, 'Stockage : les fichiers déposés sont illisibles')
    with client.session_transaction() as s:
        dump = json.dumps({k: str(v) for k, v in s.items()})
    check('PRIVATE' not in dump and 'private_key' not in dump, 'Session : aucune clé privée')
    with app.app_context():
        from sqlalchemy import inspect
        cols = {c['name'] for c in inspect(db.engine).get_columns('download_tickets')}
    check('private_key_pem' not in cols, 'Tickets de téléchargement : aucune colonne de clé')


def pages():
    assert login(state['password'])
    bad = []
    for url in ['/dashboard', '/upload-page', '/trash-page', '/activity', '/activity-page',
                '/sessions-page', '/settings-page', '/share-list-page', '/plans',
                '/change-password-page', '/api/trash', '/api/share/list']:
        code = client.get(url).status_code
        if code >= 400:
            bad.append((url, code))
    anon = app.test_client()
    for url in ['/', '/login', '/login-page', '/signup', '/signup-page', '/recover-page', '/admin/login']:
        code = anon.get(url).status_code
        if code >= 400:
            bad.append((url, code))
    check(not bad, f'Pages : toutes s\'affichent sans erreur {bad if bad else ""}')
    csp = client.get('/dashboard').headers.get('Content-Security-Policy', '')
    import re as _re
    m = _re.search(r"script-src ([^;]*);", csp)
    src = m.group(1) if m else ''
    page = client.get('/dashboard').get_data(as_text=True)
    inline_ok = all('nonce="' in tag for tag in _re.findall(r'<script(?![^>]*\ssrc=)[^>]*>', page))
    check(src.startswith("'self' 'nonce-") and "'unsafe-inline'" not in src and inline_ok,
          "CSP stricte (script-src 'self' + nonce, sans 'unsafe-inline') sur les pages qui manipulent les clés")
    for url in ['/upload', '/trash', '/sessions', '/settings', '/share/list', '/change-password', '/transfers']:
        code = client.get(url).status_code
        if code >= 400:
            bad.append((url, code))
    check(not bad, f'Pages (adresses d\'origine du design) : toutes s\'affichent {bad if bad else ""}')


def admin():
    from modules.argon2_auth import hash_auth_value
    a_email, a_pw = 'admin_test@example.com', 'Admin-Mot-De-Passe-1'
    salt = secrets.token_bytes(16)
    _, auth = pbkdf2_512(a_pw.encode(), salt)
    with app.app_context():
        db.session.add(User(username='admin_test', email=a_email, auth_hash=hash_auth_value(auth.hex()),
                            salt=salt.hex(), public_key='', encrypted_private_key='{}', is_admin=True))
        db.session.commit()
    c = app.test_client()
    s = c.post('/admin/get-salt', json={'email': a_email}).get_json()['salt']
    _, auth = pbkdf2_512(a_pw.encode(), bytes.fromhex(s))
    r = c.post('/admin/login', json={'email': a_email, 'auth_value': auth.hex()})
    check(r.status_code == 200 and r.get_json().get('ok'), 'Admin : connexion sans envoyer le mot de passe')
    bad = []
    with app.app_context():
        uid = User.query.filter_by(email=EMAIL).first().id
    for url in ['/admin', '/admin/users', f'/admin/user/{uid}', '/admin/payments', '/admin/activity',
                '/admin/promos', '/admin/api/stats', '/admin/export/users', '/admin/export/payments']:
        code = c.get(url).status_code
        if code >= 400:
            bad.append((url, code))
    check(not bad, f'Admin : toutes les pages s\'affichent {bad if bad else ""}')


def main():
    print('=' * 70)
    print('TEST DE BOUT EN BOUT : MODE ZERO-KNOWLEDGE DE VAULT')
    print('Base temporaire :', os.environ['VAULT_DB_PATH'])
    print('=' * 70)
    try:
        with app.app_context():
            db.create_all()
        signup()
        check(login(PASSWORD), 'Connexion + 2FA : clé privée déchiffrée côté client uniquement')
        upload()
        list_and_download()
        folders()
        integrity()
        share()
        recovery()
        change_password()
        folders_readable()
        no_plaintext()
        pages()
        admin()
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    ok = sum(1 for r in results if r[0])
    print('=' * 70)
    print(f'{ok}/{len(results)} vérifications réussies')
    return 0 if ok == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
