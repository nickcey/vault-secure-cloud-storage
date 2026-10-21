"""
test_pre_shamir.py — Tests de bout en bout du partage par proxy re-encryption (Umbral)
et de la récupération par contacts de confiance (Shamir 2 sur 3 : trois contacts qui acceptent, deux qui valident).

Comme test_e2e_zk.py, il simule des navigateurs honnêtes (mêmes primitives que les
scripts du navigateur, reproduites en Python) sur une base TEMPORAIRE.

Usage :  venv\\Scripts\\python test_pre_shamir.py
"""
import base64
import io
import json
import os
import secrets
import shutil
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix='vault_test_pre_')
os.environ['VAULT_DB_PATH'] = os.path.join(_TMP, 'test.db')
os.environ['VAULT_UPLOAD_FOLDER'] = os.path.join(_TMP, 'uploads')
os.environ.setdefault('FLASK_ENV', 'development')
os.environ['VAULT_DEV_SHOW_CODES'] = '1'   # tests : le serveur de courriel est absent, le code est lu à l'écran
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import umbral_pre as U                                                                  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization                       # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa, padding as rsa_padding      # noqa: E402
from cryptography.hazmat.primitives.ciphers.aead import AESGCM                         # noqa: E402
from cryptography.hazmat.primitives.kdf.hkdf import HKDF                               # noqa: E402
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC                       # noqa: E402

from app import app, PBKDF2_ITERATIONS                                                  # noqa: E402
from database.models import db, User, Delegation, FileShare                             # noqa: E402

app.config['WTF_CSRF_ENABLED'] = False
app.config['RATELIMIT_ENABLED'] = False
try:
    from app import limiter
    limiter.enabled = False
except Exception:
    pass

OAEP = rsa_padding.OAEP(mgf=rsa_padding.MGF1(algorithm=hashes.SHA256()),
                        algorithm=hashes.SHA256(), label=None)
results = []


def check(cond, label):
    results.append((bool(cond), label))
    print(('[OK]   ' if cond else '[ÉCHEC] ') + label)
    return cond


def pbkdf2_512(secret, salt):
    raw = PBKDF2HMAC(algorithm=hashes.SHA256(), length=64, salt=salt,
                     iterations=PBKDF2_ITERATIONS).derive(secret)
    return raw[:32], raw[32:]


def aes_wrap_json(key, data):
    iv = secrets.token_bytes(12)
    return json.dumps({'iv': iv.hex(), 'ct': base64.b64encode(AESGCM(key).encrypt(iv, data, None)).decode()})


def aes_unwrap_json(key, payload):
    p = json.loads(payload)
    return AESGCM(key).decrypt(bytes.fromhex(p['iv']), base64.b64decode(p['ct']), None)


def hkdf(key, info):
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=b'', info=info).derive(key)


class Browser:
    """Un utilisateur et son navigateur (clés gardées « dans le navigateur »)."""

    def __init__(self, name):
        self.c = app.test_client()
        self.email = f'{name}_{secrets.token_hex(3)}@example.com'
        self.password = 'MotDePasse-' + name

    def post(self, url, payload=None, **kw):
        r = self.c.post(url, json=payload, **kw) if payload is not None else self.c.post(url, **kw)
        try:
            return r, r.get_json() or {}
        except Exception:
            return r, {}

    def signup(self):
        self.c.post('/signup', data={'username': self.email.split('@')[0], 'email': self.email})
        with self.c.session_transaction() as s:
            otp = s.get('signup_otp')
        self.c.post('/verify-signup-otp', data={'otp_code': otp})
        with self.c.session_transaction() as s:
            msgs = [m for _, m in s.get('_flashes', [])]
        temp_pw = next(m.split(': ', 1)[1] for m in msgs if 'Mot de passe temporaire' in m)
        r, b = self.post('/get-salt', {'email': self.email})
        _, temp_auth = pbkdf2_512(temp_pw.encode(), bytes.fromhex(b['salt']))
        salt = secrets.token_bytes(16)
        self.account_key, auth = pbkdf2_512(self.password.encode(), salt)
        self.rsa = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.pkcs8 = self.rsa.private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.PKCS8,
                                            serialization.NoEncryption())
        spki = self.rsa.public_key().public_bytes(serialization.Encoding.DER,
                                                  serialization.PublicFormat.SubjectPublicKeyInfo)
        rec_key, rec_auth = pbkdf2_512(b'phrase de test', b'vault-recovery:' + self.email.encode())
        r, b = self.post('/api/setup-keys', {
            'current_auth_value': temp_auth.hex(), 'auth_value': auth.hex(),
            'recovery_auth_value': rec_auth.hex(), 'salt': salt.hex(),
            'public_key': base64.b64encode(spki).decode(),
            'encrypted_private_key': aes_wrap_json(self.account_key, self.pkcs8),
            'recovery_wrapped_key': aes_wrap_json(rec_key, self.pkcs8)})
        return r.status_code == 200

    def umbral_setup(self):
        """Comme vault-pre.js : clés Umbral créées puis chiffrées RSA-OAEP pour soi-même."""
        self.usk, sign_sk = U.SecretKey.random(), U.SecretKey.random()
        self.signer = U.Signer(sign_sk)
        enc = self.rsa.public_key().encrypt(self.usk.to_be_bytes() + sign_sk.to_be_bytes(), OAEP)
        r, b = self.post('/api/umbral-keys', {
            'umbral_public_key': bytes(self.usk.public_key().to_compressed_bytes()).hex(),
            'verifying_key': bytes(self.signer.verifying_key().to_compressed_bytes()).hex(),
            'encrypted_umbral_keys': base64.b64encode(enc).decode()})
        return r.status_code == 200

    def upload(self, content, name):
        file_key = secrets.token_bytes(32)
        iv = secrets.token_bytes(12)
        blob = iv + AESGCM(file_key).encrypt(iv, content, None)
        meta = json.dumps({'filename': name, 'plaintext_size': len(content)}).encode()
        miv = secrets.token_bytes(12)
        enc_meta = base64.b64encode(miv + AESGCM(hkdf(file_key, b'vault-metadata-v1')).encrypt(miv, meta, None)).decode()
        r = self.c.post('/upload', data={
            'file': (io.BytesIO(blob), 'payload.enc'), 'uuid': secrets.token_hex(16), 'aes_iv': iv.hex(),
            'encrypted_file_key': base64.b64encode(self.rsa.public_key().encrypt(file_key, OAEP)).decode(),
            'encrypted_metadata': enc_meta, 'original_size': len(content), 'padded_size': len(blob),
        }, content_type='multipart/form-data')
        return r.get_json()['file_id'], file_key


def pre_tests(alice, bob, eve):
    content = b'Rapport confidentiel partage par proxy re-encryption ' + secrets.token_bytes(2000)
    fid, file_key = alice.upload(content, 'rapport.pdf')

    r, prof = alice.post('/api/users/lookup', {'email': bob.email})
    check(r.status_code == 200 and prof.get('umbral_public_key') and not prof.get('has_delegation'),
          'PRE : le propriétaire obtient les clés PUBLIQUES du destinataire')
    bob_pk = U.PublicKey.from_compressed_bytes(bytes.fromhex(prof['umbral_public_key']))
    capsule, ct = U.encrypt(alice.usk.public_key(), file_key)
    kfrags = U.generate_kfrags(delegating_sk=alice.usk, receiving_pk=bob_pk, signer=alice.signer,
                               threshold=1, shares=1, sign_delegating_key=True, sign_receiving_key=True)

    # Un kfrag forgé (signé par quelqu'un d'autre) doit être refusé par le serveur
    fake = U.generate_kfrags(delegating_sk=alice.usk, receiving_pk=bob_pk, signer=U.Signer(U.SecretKey.random()),
                             threshold=1, shares=1, sign_delegating_key=True, sign_receiving_key=True)
    r, b = alice.post(f'/api/files/{fid}/share-user', {
        'recipient_id': prof['id'], 'capsule': base64.b64encode(bytes(capsule)).decode(),
        'umbral_ciphertext': base64.b64encode(bytes(ct)).decode(), 'kfrag': base64.b64encode(bytes(fake[0])).decode()})
    check(r.status_code == 400, 'PRE : un fragment de re-chiffrement non signé par le propriétaire est refusé')

    r, b = alice.post(f'/api/files/{fid}/share-user', {
        'recipient_id': prof['id'], 'capsule': base64.b64encode(bytes(capsule)).decode(),
        'umbral_ciphertext': base64.b64encode(bytes(ct)).decode(), 'kfrag': base64.b64encode(bytes(kfrags[0])).decode()})
    check(r.status_code == 200, 'PRE : partage enregistré (kfrag vérifié par le serveur)')

    r = bob.c.get('/api/shared-with-me')
    items = r.get_json()['files']
    check(len(items) == 1, 'PRE : le fichier apparaît chez le destinataire')
    it = items[0]
    pk = lambda h: U.PublicKey.from_compressed_bytes(bytes.fromhex(h))
    cap = U.Capsule.from_bytes(base64.b64decode(it['capsule']))
    vcf = U.CapsuleFrag.from_bytes(base64.b64decode(it['cfrag'])).verify(
        cap, pk(it['owner']['verifying_key']), pk(it['owner']['umbral_public_key']),
        bob.usk.public_key())
    got_key = U.decrypt_reencrypted(bob.usk, pk(it['owner']['umbral_public_key']), cap, [vcf],
                                    base64.b64decode(it['umbral_ciphertext']))
    check(bytes(got_key) == file_key, 'PRE : le destinataire retrouve la clé du fichier (cfrag vérifié)')
    blob = bob.c.get(f"/api/shared-with-me/{it['share_id']}/blob").data
    check(AESGCM(bytes(got_key)).decrypt(blob[:12], blob[12:], None) == content,
          'PRE : le destinataire déchiffre le contenu du fichier')

    # Le serveur seul ne peut rien : la capsule et le cfrag ne s'ouvrent qu'avec une clé secrète
    try:
        U.decrypt_reencrypted(U.SecretKey.random(), pk(it['owner']['umbral_public_key']), cap, [vcf],
                              base64.b64decode(it['umbral_ciphertext']))
        leaked = True
    except Exception:
        leaked = False
    check(not leaked, 'PRE : sans la clé secrète du destinataire, le résultat du re-chiffrement est inutilisable')
    with app.app_context():
        raw = json.dumps([str(v) for d in Delegation.query.all() for v in (d.kfrag,)])
    check(file_key.hex() not in raw, 'PRE : aucune clé de fichier en clair côté serveur')

    r = eve.c.get('/api/shared-with-me')
    check(r.get_json()['files'] == [], 'PRE : un tiers ne voit rien')
    r = eve.c.get(f"/api/shared-with-me/{it['share_id']}/blob")
    check(r.status_code == 404, 'PRE : un tiers ne peut pas télécharger le fichier partagé')

    # Deuxième fichier : la délégation existante est réutilisée (pas de nouveau kfrag)
    fid2, key2 = alice.upload(b'second', 'notes.txt')
    r, prof2 = alice.post('/api/users/lookup', {'email': bob.email})
    cap2, ct2 = U.encrypt(alice.usk.public_key(), key2)
    r, b = alice.post(f'/api/files/{fid2}/share-user', {
        'recipient_id': prof['id'], 'capsule': base64.b64encode(bytes(cap2)).decode(),
        'umbral_ciphertext': base64.b64encode(bytes(ct2)).decode()})
    check(prof2.get('has_delegation') and r.status_code == 200 and len(bob.c.get('/api/shared-with-me').get_json()['files']) == 2,
          'PRE : la même autorisation sert pour un second fichier')

    shares = alice.c.get('/api/my-user-shares').get_json()['shares']
    for s in shares:
        alice.post(f"/api/user-shares/{s['share_id']}/revoke", {})
    with app.app_context():
        no_left = Delegation.query.count() == 0 and FileShare.query.count() == 0
    check(bob.c.get('/api/shared-with-me').get_json()['files'] == [] and no_left,
          'PRE : révocation — plus de fichier, la clé de re-chiffrement est supprimée')


# ── Shamir 2 sur 3 (même arithmétique que vault-shamir.js) ──
EXP, LOG = [0] * 510, [0] * 256
_x = 1
for _i in range(255):
    EXP[_i] = _x; LOG[_x] = _i
    _y = _x << 1
    if _y & 0x100:
        _y ^= 0x11b
    _x = _y ^ _x
for _i in range(255, 510):
    EXP[_i] = EXP[_i - 255]
gmul = lambda a, b: 0 if a == 0 or b == 0 else EXP[LOG[a] + LOG[b]]
gdiv = lambda a, b: 0 if a == 0 else EXP[(LOG[a] + 255 - LOG[b]) % 255]


def split(secret, n=5, k=3):
    coefs = [secrets.token_bytes(len(secret)) for _ in range(k - 1)]
    out = {}
    for x in range(1, n + 1):
        y = bytearray()
        for i, sb in enumerate(secret):
            acc = 0
            for d in range(len(coefs) - 1, -1, -1):
                acc = gmul(acc ^ coefs[d][i], x)
            y.append(acc ^ sb)
        out[x] = bytes(y)
    return out


def combine(parts):
    out = bytearray(len(parts[0][1]))
    for j, (xj, yj) in enumerate(parts):
        l = 1
        for m, (xm, _) in enumerate(parts):
            if m != j:
                l = gmul(l, gdiv(xm, xm ^ xj))
        for i in range(len(out)):
            out[i] ^= gmul(yj[i], l)
    return bytes(out)


def shamir_tests(alice, contacts):
    from itertools import combinations
    S = secrets.token_bytes(32)
    parts = split(S, 3, 2)
    check(all(combine([(x, parts[x]) for x in duo]) == S for duo in combinations(range(1, 4), 2)),
          'Shamir : deux parts quelconques sur trois reconstituent le secret')
    key, auth = hkdf(S, b'vault-shamir-key-v1'), hkdf(S, b'vault-shamir-auth-v1')
    profiles = [alice.post('/api/users/lookup', {'email': c.email})[1] for c in contacts]
    load = lambda der: serialization.load_der_public_key(der)
    payload = [{'contact_id': p['id'], 'share_index': n + 1,
                'encrypted_share': base64.b64encode(load(base64.b64decode(p['public_key'])).encrypt(parts[n + 1], OAEP)).decode()}
               for n, p in enumerate(profiles)]
    r, b = alice.post('/api/recovery-contacts', {'contacts': payload[:2], 'shamir_wrapped_key': 'x', 'shamir_auth_value': auth.hex()})
    check(r.status_code == 400, 'Shamir : configuration refusée avec moins de 3 contacts')
    r, b = alice.post('/api/recovery-contacts', {
        'contacts': payload, 'shamir_wrapped_key': aes_wrap_json(key, alice.pkcs8), 'shamir_auth_value': auth.hex()})
    st = alice.c.get('/api/recovery-contacts').get_json()
    check(r.status_code == 200 and not st['ready'] and all(c['status'] == 'pending' for c in st['contacts']),
          'Shamir : trois invitations envoyées, récupération pas encore active')
    with app.app_context():
        u = User.query.filter_by(email=alice.email).first()
        stored = json.dumps([u.shamir_wrapped_key, u.shamir_auth_hash])
    check(S.hex() not in stored and all(parts[x].hex() not in stored for x in parts),
          'Shamir : aucune part ni secret en clair sur le serveur')

    lost = Browser('alice-perdue'); lost.email = alice.email
    r, b = lost.post('/api/shamir-recovery/start', {'email': alice.email})
    check(not b.get('dev_otp'), 'Shamir : aucune récupération possible tant que les contacts n\'ont pas accepté')

    inv = [c.c.get('/api/recovery-invitations').get_json()['invitations'] for c in contacts]
    check(all(len(x) == 1 for x in inv), 'Shamir : chaque contact voit l\'invitation dans son compte')
    contacts[0].post(f"/api/recovery-invitations/{inv[0][0]['id']}/respond", {'accept': True})
    contacts[1].post(f"/api/recovery-invitations/{inv[1][0]['id']}/respond", {'accept': False})
    st = alice.c.get('/api/recovery-contacts').get_json()
    check(not st['ready'] and [c['status'] for c in st['contacts']] == ['accepted', 'declined', 'pending'],
          'Shamir : réponses enregistrées (accepté / refusé / en attente)')
    contacts[2].post(f"/api/recovery-invitations/{inv[2][0]['id']}/respond", {'accept': True})
    check(alice.c.get('/api/recovery-contacts').get_json()['ready'], 'Shamir : récupération active dès 2 acceptations')

    r, b = lost.post('/api/shamir-recovery/start', {'email': alice.email})
    temp = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    temp_pub = base64.b64encode(temp.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)).decode()
    r, bad = lost.post('/api/shamir-recovery/verify', {'otp_code': '000000', 'temp_public_key': temp_pub})
    check(r.status_code == 400, 'Shamir : demande refusée sans le code reçu par email')
    r, v = lost.post('/api/shamir-recovery/verify', {'otp_code': b.get('dev_otp'), 'temp_public_key': temp_pub})
    check(r.status_code == 200 and v.get('token') and v.get('threshold') == 2, 'Shamir : demande ouverte après le code email')
    seen = [bool(c.c.get('/api/recovery-requests').get_json()['requests']) for c in contacts]
    check(seen == [True, False, True], 'Shamir : seuls les contacts ayant accepté reçoivent la demande')

    def approve(c):
        q = c.c.get('/api/recovery-requests').get_json()['requests'][0]
        share = c.rsa.decrypt(base64.b64decode(q['encrypted_share']), OAEP)
        enc = load(base64.b64decode(q['temp_public_key'])).encrypt(share, OAEP)
        c.post(f"/api/recovery-requests/{q['request_id']}/approve", {'encrypted_share': base64.b64encode(enc).decode()})

    approve(contacts[0])
    _, st = lost.post('/api/shamir-recovery/status', {'token': v['token']})
    got = [(a['share_index'], temp.decrypt(base64.b64decode(a['encrypted_share']), OAEP)) for a in st['approvals']]
    try:
        one_ok = aes_unwrap_json(hkdf(got[0][1], b'vault-shamir-key-v1'), st['shamir_wrapped_key']) == alice.pkcs8
    except Exception:
        one_ok = False
    check(len(got) == 1 and not one_ok, 'Shamir : une seule validation ne suffit pas')
    approve(contacts[2])
    _, st = lost.post('/api/shamir-recovery/status', {'token': v['token']})
    got = [(a['share_index'], temp.decrypt(base64.b64decode(a['encrypted_share']), OAEP)) for a in st['approvals']]
    S2 = combine(got)
    k2, auth3 = hkdf(S2, b'vault-shamir-key-v1'), hkdf(S2, b'vault-shamir-auth-v1')
    pkcs8 = aes_unwrap_json(k2, st['shamir_wrapped_key'])
    check(len(got) == 2 and pkcs8 == alice.pkcs8, 'Shamir : clé privée retrouvée avec 2 validations sur 3')

    new_pw = 'Nouveau-Mot-De-Passe-1'
    salt = secrets.token_bytes(16)
    acc, auth_new = pbkdf2_512(new_pw.encode(), salt)
    r, b = lost.post('/api/shamir-recovery/complete', {
        'token': v['token'], 'shamir_auth_value': secrets.token_hex(32), 'auth_value': auth_new.hex(),
        'salt': salt.hex(), 'encrypted_private_key': aes_wrap_json(acc, pkcs8)})
    check(r.status_code == 401, 'Shamir : finalisation refusée sans la vraie clé reconstituée')
    r, b = lost.post('/api/shamir-recovery/complete', {
        'token': v['token'], 'shamir_auth_value': auth3.hex(), 'auth_value': auth_new.hex(),
        'salt': salt.hex(), 'encrypted_private_key': aes_wrap_json(acc, pkcs8)})
    check(r.status_code == 200, 'Shamir : compte récupéré, nouveau mot de passe enregistré')
    r, s = lost.post('/get-salt', {'email': alice.email})
    _, auth_login = pbkdf2_512(new_pw.encode(), bytes.fromhex(s['salt']))
    r, b = lost.post('/login', {'email': alice.email, 'auth_value': auth_login.hex()})
    check(r.status_code == 200, 'Shamir : connexion avec le nouveau mot de passe')
    r, _ = lost.post('/api/shamir-recovery/status', {'token': v['token']})
    check(r.status_code == 404, 'Shamir : la demande est close après usage')


def main():
    print('=' * 70)
    print('TEST : PARTAGE PAR PROXY RE-ENCRYPTION ET RÉCUPÉRATION PAR CONTACTS')
    print('=' * 70)
    try:
        with app.app_context():
            db.create_all()
        alice, eve = Browser('alice'), Browser('eve')
        contacts = [Browser(n) for n in ('bob', 'carol', 'dave')]
        everyone = [alice, eve] + contacts
        check(all(u.signup() for u in everyone), 'Cinq comptes créés')
        check(all(u.umbral_setup() for u in everyone), 'Clés Umbral enregistrées (secrets chiffrés pour soi)')
        pre_tests(alice, contacts[0], eve)
        shamir_tests(alice, contacts)
    finally:
        shutil.rmtree(_TMP, ignore_errors=True)
    ok = sum(1 for r in results if r[0])
    print('=' * 70)
    print(f'{ok}/{len(results)} vérifications réussies')
    return 0 if ok == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
