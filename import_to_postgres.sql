-- Script SQL pour créer les tables PostgreSQL
-- Généré automatiquement pour Vault Secure Cloud Storage

-- Supprimer les tables si elles existent (pour réimport propre)
DROP TABLE IF EXISTS shared_link CASCADE;
DROP TABLE IF EXISTS promo_code CASCADE;
DROP TABLE IF EXISTS download_token CASCADE;
DROP TABLE IF EXISTS payment CASCADE;
DROP TABLE IF EXISTS active_session CASCADE;
DROP TABLE IF EXISTS activity_log CASCADE;
DROP TABLE IF EXISTS file_metadata CASCADE;
DROP TABLE IF EXISTS "user" CASCADE;

-- Table User
CREATE TABLE "user" (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    salt VARCHAR(255) NOT NULL,
    encrypted_private_key TEXT NOT NULL,
    recovery_hint TEXT,
    plan VARCHAR(50) DEFAULT 'free',
    storage_used BIGINT DEFAULT 0,
    subscription_expiry TIMESTAMP,
    otp_secret VARCHAR(10),
    otp_expiry INTEGER DEFAULT 0,
    is_temp_password BOOLEAN DEFAULT FALSE,
    is_admin BOOLEAN DEFAULT FALSE,
    is_suspended BOOLEAN DEFAULT FALSE,
    language VARCHAR(10) DEFAULT 'fr',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table FileMetadata
CREATE TABLE file_metadata (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    original_filename VARCHAR(255) NOT NULL,
    encrypted_filename VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    encrypted_key TEXT NOT NULL,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP
);

-- Table ActivityLog
CREATE TABLE activity_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    action VARCHAR(255) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45)
);

-- Table ActiveSession
CREATE TABLE active_session (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    session_token VARCHAR(255) NOT NULL UNIQUE,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table Payment
CREATE TABLE payment (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    plan VARCHAR(50) NOT NULL,
    duration VARCHAR(20) NOT NULL,
    amount FLOAT NOT NULL,
    reference VARCHAR(255) NOT NULL UNIQUE,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    paid_at TIMESTAMP
);

-- Table DownloadToken
CREATE TABLE download_token (
    id SERIAL PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES file_metadata(id) ON DELETE CASCADE,
    token VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT FALSE
);

-- Table PromoCode
CREATE TABLE promo_code (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    discount_percent INTEGER NOT NULL,
    max_uses INTEGER DEFAULT 0,
    current_uses INTEGER DEFAULT 0,
    valid_from TIMESTAMP,
    valid_until TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Table SharedLink
CREATE TABLE shared_link (
    id SERIAL PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES file_metadata(id) ON DELETE CASCADE,
    share_token VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255),
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    max_downloads INTEGER DEFAULT 0,
    current_downloads INTEGER DEFAULT 0
);

-- Index pour optimisation
CREATE INDEX idx_file_user_id ON file_metadata(user_id);
CREATE INDEX idx_file_deleted ON file_metadata(is_deleted);
CREATE INDEX idx_activity_user_id ON activity_log(user_id);
CREATE INDEX idx_session_token ON active_session(session_token);
CREATE INDEX idx_payment_user_id ON payment(user_id);
CREATE INDEX idx_payment_reference ON payment(reference);

-- Afficher les tables créées
\dt
