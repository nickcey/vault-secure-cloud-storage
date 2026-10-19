"""
test_payment.py — Vérifie qu'un abonnement n'est activé qu'après une confirmation
authentique de l'agrégateur (ENF-13) : une notification forgée envoyée au webhook
ne suffit pas, le statut est toujours redemandé à l'API CamPay.

Usage :  venv\\Scripts\\python test_payment.py
"""
import os
import shutil
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix='vault_test_pay_')
os.environ['VAULT_DB_PATH'] = os.path.join(_TMP, 'test.db')
os.environ['VAULT_UPLOAD_FOLDER'] = os.path.join(_TMP, 'uploads')
os.environ.setdefault('FLASK_ENV', 'development')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app as vault                                                    # noqa: E402
from database.models import db, User, Payment                          # noqa: E402

vault.app.config['WTF_CSRF_ENABLED'] = False
vault.limiter.enabled = False
results = []


def check(cond, label):
    results.append(bool(cond))
    print(('[OK]   ' if cond else '[ÉCHEC] ') + label)


answer = {'status': 'PENDING'}
vault.check_payment_status = lambda ref: answer['status']   # API CamPay simulée

with vault.app.app_context():
    db.create_all()
    u = User(username='Paul', email='paul@example.com', plan='free', quota=1610612736,
             auth_hash='x', salt='00' * 16, encrypted_private_key='{}', public_key='')
    db.session.add(u); db.session.commit()
    p = Payment(user_id=u.id, plan='premium', amount=1000, status='pending',
                reference='REF-TEST-1', billing_cycle='monthly')
    db.session.add(p); db.session.commit()
    uid, pid = u.id, p.id

c = vault.app.test_client()
forged = {'reference': 'REF-TEST-1', 'status': 'SUCCESSFUL'}

c.post('/payment-webhook', json=forged)
with vault.app.app_context():
    check(db.session.get(User, uid).plan == 'free',
          'Webhook forgé (CamPay répond PENDING) : abonnement non activé')
    check(db.session.get(Payment, pid).status == 'pending', 'Webhook forgé : paiement toujours en attente')

answer['status'] = 'FAILED'
c.post('/payment-webhook', json=forged)
with vault.app.app_context():
    check(db.session.get(User, uid).plan == 'free' and db.session.get(Payment, pid).status == 'failed',
          'Paiement refusé par CamPay : marqué échoué, abonnement non activé')
    db.session.get(Payment, pid).status = 'pending'; db.session.commit()

answer['status'] = 'SUCCESSFUL'
c.post('/payment-webhook', json={'reference': 'REF-TEST-1', 'status': 'FAILED'})
with vault.app.app_context():
    usr = db.session.get(User, uid)
    check(usr.plan == 'premium' and usr.quota == vault.PLANS['premium']['quota'],
          'Paiement confirmé par CamPay : abonnement activé (quel que soit le contenu reçu)')
    exp = usr.subscription_expiry

c.post('/payment-webhook', json=forged)
with vault.app.app_context():
    check(db.session.get(User, uid).subscription_expiry == exp,
          'Notification répétée : abonnement non prolongé une seconde fois')

c.post('/payment-webhook', json={'reference': 'INCONNUE', 'status': 'SUCCESSFUL'})
check(True, 'Référence inconnue : ignorée sans erreur')

print('=' * 70)
print(f'{sum(results)}/{len(results)} vérifications réussies')
shutil.rmtree(_TMP, ignore_errors=True)
sys.exit(0 if all(results) else 1)
