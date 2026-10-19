"""
Modèles de base — Vault Secure Cloud Storage (zero-knowledge)

Le serveur ne stocke JAMAIS :
- le mot de passe (seul un Argon2id de la valeur d'authentification dérivée client) ;
- une clé privée en clair (seulement une enveloppe AES-GCM incompréhensible pour lui) ;
- une clé de fichier en clair (seulement une enveloppe RSA-OAEP) ;
- un nom de fichier en clair (seulement du JSON chiffré AES-GCM/HKDF).
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # Argon2id de la VALEUR D'AUTHENTIFICATION (256 bits dérivés côté client, en hex)
    auth_hash = db.Column(db.String(200), nullable=False)
    # Sel PBKDF2 (16 octets, hex) — public, sert au navigateur pour dériver ses clés
    salt = db.Column(db.String(64), nullable=False)
    # Clé privée RSA chiffrée AES-256-GCM côté client avec la clé de compte
    # Format JSON : {"ct": b64, "iv": b64, "ieee": "11"}
    encrypted_private_key = db.Column(db.Text, nullable=False)
    # Clé publique RSA-OAEP 2048 (SPKI DER, b64)
    public_key = db.Column(db.Text, nullable=False)
    # Clé de compte re-chiffrée côté client par la clé de récupération BIP-39
    recovery_wrapped_key = db.Column(db.Text, nullable=True)
    # Argon2id de la preuve de possession de la phrase de récupération
    # (256 bits dérivés côté client de la phrase BIP-39 ; la phrase reste dans le navigateur)
    recovery_auth_hash = db.Column(db.String(200), nullable=True)
    # 2FA par e-mail (inchangée)
    otp_secret = db.Column(db.String(32), default='')
    otp_expiry = db.Column(db.Integer, default=0)
    is_temp_password = db.Column(db.Boolean, default=False)
    # ── Proxy re-encryption (Umbral) ──
    # Clé publique Umbral et clé de vérification des signatures (compressées, hex) : publiques
    umbral_public_key = db.Column(db.Text, nullable=True)
    verifying_key = db.Column(db.Text, nullable=True)
    # Clé secrète Umbral || clé de signature, chiffrées RSA-OAEP avec la clé publique
    # RSA du compte (b64) : seul le navigateur du titulaire peut les déchiffrer
    encrypted_umbral_keys = db.Column(db.Text, nullable=True)
    # ── Récupération par contacts de confiance (Shamir 2 sur 3) ──
    # Copie de la clé privée chiffrée avec la clé de récupération Shamir (JSON AES-GCM)
    shamir_wrapped_key = db.Column(db.Text, nullable=True)
    # Argon2id de la preuve de possession de la clé Shamir reconstituée
    shamir_auth_hash = db.Column(db.String(200), nullable=True)
    shamir_configured_at = db.Column(db.DateTime, nullable=True)
    # Arborescence des dossiers : un index chiffré dans le navigateur (AES-256-GCM).
    # Le serveur ne voit ni les noms des dossiers ni le rangement des fichiers.
    folder_index = db.Column(db.Text, nullable=True)            # {"iv": hex, "ct": b64}
    folder_index_key = db.Column(db.Text, nullable=True)        # clé de l'index, RSA-OAEP (clé publique du compte)
    folder_index_version = db.Column(db.Integer, default=0)
    is_admin = db.Column(db.Boolean, default=False)
    is_suspended = db.Column(db.Boolean, default=False)
    plan = db.Column(db.String(20), default='free')
    quota = db.Column(db.BigInteger, default=1610612736)
    subscription_expiry = db.Column(db.DateTime, nullable=True)
    grace_period_end = db.Column(db.DateTime, nullable=True)
    language = db.Column(db.String(5), default='fr')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    files = db.relationship('FileMetadata', backref='owner', lazy=True)
    activities = db.relationship('ActivityLog', backref='user', lazy=True)
    sessions = db.relationship('ActiveSession', backref='user', lazy=True)
    payments = db.relationship('Payment', backref='user', lazy=True)


class FileMetadata(db.Model):
    """
    Fichier : tout est chiffré côté client. Le serveur n'a que :
    - l'UUID opaque du fichier, le nom du blob (UUID.enc) ;
    - les métadonnées chiffrées AES-GCM (nom, taille, mime, date) ;
    - la clé de fichier enveloppée RSA-OAEP avec la clé publique du propriétaire ;
    - le hash SHA-256 côté client (integrité, pour rejet du fichier corrompu).
    """
    __tablename__ = 'files'
    id = db.Column(db.Integer, primary_key=True)

    uuid = db.Column(db.String(64), nullable=False, unique=False, index=True)
    stored_filename = db.Column(db.String(120), nullable=False)  # "<uuid>.enc"
    stored_size = db.Column(db.BigInteger, nullable=False)       # taille sur disque (padding inclus)
    original_size = db.Column(db.BigInteger, nullable=False)     # taille plaintext (déclarée par le client)
    padded_size = db.Column(db.BigInteger, nullable=True)        # taille paddée (checksum)

    # AES-256-GCM : iv (12 octets, hex) || ciphertext || tag (16 octets) — padding compris
    aes_iv = db.Column(db.String(64), nullable=False)

    # Clé de fichier AES-256 enveloppée RSA-OAEP-SHA256 du propriétaire (b64)
    encrypted_file_key = db.Column(db.Text, nullable=False)

    # Métadonnées chiffrées AES-GCM avec clé HKDF dérivée de la clé de fichier
    # Format b64 : iv(12) || ciphertext || tag(16)
    encrypted_metadata = db.Column(db.Text, nullable=False)
    metadata_sha256 = db.Column(db.String(64), nullable=True)  # SHA-256 du plaintext métadonnées (optionnel)

    # SHA-256 du PLAINTEXT du contenu (optionnel, rejet de la modification)
    content_sha256 = db.Column(db.String(64), nullable=True)

    # Capsule Umbral : la clé de fichier chiffrée pour la clé publique Umbral du
    # propriétaire (b64). Le serveur la re-chiffre pour un destinataire autorisé.
    umbral_capsule = db.Column(db.Text, nullable=True)
    umbral_ciphertext = db.Column(db.Text, nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)
    deleted_at = db.Column(db.DateTime, nullable=True)


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    # UUID seulement : aucun nom de fichier en clair dans la base
    file_uuid = db.Column(db.String(64), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class ActiveSession(db.Model):
    __tablename__ = 'active_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_token = db.Column(db.String(64), unique=True, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)


class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reference = db.Column(db.String(100), unique=True, nullable=False)
    plan = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending')
    operator = db.Column(db.String(20), nullable=True)
    billing_cycle = db.Column(db.String(10), default='monthly')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime, nullable=True)


class PromoCode(db.Model):
    __tablename__ = 'promo_codes'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    discount_percent = db.Column(db.Integer, nullable=False)
    applicable_plans = db.Column(db.String(100), default='all')
    max_uses = db.Column(db.Integer, default=0)
    uses_count = db.Column(db.Integer, default=0)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.String(200), nullable=True)


class SharedLink(db.Model):
    """
    Lien de partage. La clé de fichier transite UNIQUEMENT dans le fragment de
    l'URL (après #), qui ne quitte jamais le navigateur. Côté serveur :
    - token opaque, dates et limites de téléchargement ; LE SERVEUR NE CONNAÎT
      PAS LA CLÉ, donc il n'a rien à chiffrer.
    """
    __tablename__ = 'shared_links'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    max_downloads = db.Column(db.Integer, default=0)
    download_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DownloadTicket(db.Model):
    """
    Ancienne table download_tokens remplacée (elle stockait private_key_pem en clair).
    Ticket de téléchargement à usage unique et AVEUGLE : le client déchiffre seul.
    """
    __tablename__ = 'download_tickets'
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False)
    file_uuid = db.Column(db.String(64), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    expiry = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Delegation(db.Model):
    """
    Autorisation de re-chiffrement du propriétaire vers un destinataire (kfrag Umbral,
    signé par le propriétaire). Une seule par couple, réutilisée pour tous les fichiers
    partagés entre eux. Le serveur ne peut rien déchiffrer avec : il ne fait que transformer.
    """
    __tablename__ = 'delegations'
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    kfrag = db.Column(db.Text, nullable=False)          # KeyFrag Umbral (b64)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('owner_id', 'recipient_id', name='uq_delegation_pair'),)


class FileShare(db.Model):
    """Fichier partagé avec un utilisateur Vault (par proxy re-encryption)."""
    __tablename__ = 'file_shares'
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False, index=True)
    delegation_id = db.Column(db.Integer, db.ForeignKey('delegations.id'), nullable=False, index=True)
    # Chemin du fichier dans le dossier partagé, chiffré pour le destinataire (AES-GCM,
    # clé enveloppée par sa clé publique RSA) : le serveur ne le lit pas.
    folder_label = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('file_id', 'delegation_id', name='uq_file_share'),)


class RecoveryShare(db.Model):
    """Part Shamir confiée à un contact, chiffrée avec SA clé publique RSA (b64).
    Elle ne sert que si le contact a accepté l'invitation."""
    __tablename__ = 'recovery_shares'
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    share_index = db.Column(db.Integer, nullable=False)   # abscisse x de la part (1 à 3)
    encrypted_share = db.Column(db.Text, nullable=False)
    # Le contact doit accepter d'être contact de récupération : pending / accepted / declined
    status = db.Column(db.String(20), default='pending')
    responded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RecoveryRequest(db.Model):
    """
    Demande de récupération par contacts de confiance. Ouverte seulement après un code
    reçu par email. La clé publique temporaire vient du navigateur du demandeur ; les
    contacts y rechiffrent leur part.
    """
    __tablename__ = 'recovery_requests'
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    token = db.Column(db.String(64), unique=True, nullable=False)   # identifie la demande côté demandeur
    temp_public_key = db.Column(db.Text, nullable=False)            # RSA-OAEP SPKI (b64)
    status = db.Column(db.String(20), default='pending')            # pending / completed / cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)


class RecoveryApproval(db.Model):
    """Part d'un contact rechiffrée pour la clé temporaire du demandeur."""
    __tablename__ = 'recovery_approvals'
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey('recovery_requests.id'), nullable=False, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    share_index = db.Column(db.Integer, nullable=False)
    encrypted_share = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
