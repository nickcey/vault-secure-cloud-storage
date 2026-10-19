/**
 * vault-crypto.js — Cryptographie client Vault (100 % Web Crypto API)
 * ===================================================================
 * Le navigateur seul détient les secrets. Utilisé par toutes les pages
 * (login, signup, upload, dashboard, récupération, partage).
 * Servi depuis /static/js — CSP : script-src 'self', aucun CDN.
 *
 * Primitives :
 * - PBKDF2-SHA256, 600 000 itérations, 512 bits (256 compte + 256 auth)
 * - RSA-OAEP 2048 bits SHA-256 (paire de clés du compte)
 * - AES-256-GCM (fichiers, clé privée, métadonnées, clé de compte)
 * - HKDF-SHA256 (clé de métadonnées dérivée de la clé de fichier)
 * - BIP-39 (génération client de la phrase mnémonique — vault-bip39.js)
 */

const VAULT_PBKDF2_ITERATIONS = 600000;

// ── Utilitaires d'encodage ─────────────────────────────────────

function b64ToBuf(b64) {
  const bin = atob(b64);
  const buf = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
  return buf;
}

function bufToB64(buf) {
  let bin = '';
  const bytes = new Uint8Array(buf);
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK));
  }
  return btoa(bin);
}

function hexToBuf(hex) {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = parseInt(hex.substr(i * 2, 2), 16);
  return out;
}

function bufToHex(buf) {
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
}

function strToBuf(s) { return new TextEncoder().encode(s); }
function bufToStr(buf) { return new TextDecoder().decode(buf); }

// ── PBKDF2 : dérivation 512 bits (compte 256 + authentification 256) ──

/**
 * Dérive 512 bits du mot de passe via PBKDF2-SHA256 (600 000 itérations).
 * @param {string} password
 * @param {Uint8Array} saltBytes
 * @returns {Promise<{accountKey: Uint8Array(32), authValue: Uint8Array(32)}>}
 */
async function vaultDeriveKeys(password, saltBytes) {
  const baseKey = await crypto.subtle.importKey('raw', strToBuf(password), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', hash: 'SHA-256', salt: saltBytes, iterations: VAULT_PBKDF2_ITERATIONS },
    baseKey, 512);
  const raw = new Uint8Array(bits);
  return {
    accountKey: raw.slice(0, 32),
    authValue: raw.slice(32, 64),
  };
}

// ── AES-GCM helpers ───────────────────────────────────────────

async function vaultImportAesKey(rawBytes) {
  return crypto.subtle.importKey('raw', rawBytes, { name: 'AES-GCM' }, false, ['encrypt', 'decrypt']);
}

/**
 * Chiffre AES-256-GCM. Retourne { iv: hex, ct: b64 } (tag inclus dans ct comme Web Crypto).
 */
async function vaultAesEncryptBytes(keyObj, plaintextBytes) {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, keyObj, plaintextBytes);
  return { iv: bufToHex(iv), ct: bufToB64(ct) };
}

/**
 * Déchiffre AES-GCM. payload = { iv: hex, ct: b64 }.
 */
async function vaultAesDecryptBytes(keyObj, payload) {
  const iv = hexToBuf(payload.iv);
  const ct = b64ToBuf(payload.ct);
  const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, keyObj, ct);
  return new Uint8Array(pt);
}

// ── RSA-OAEP 2048 / SHA-256 ───────────────────────────────────

async function vaultGenerateKeyPair() {
  const kp = await crypto.subtle.generateKey(
    { name: 'RSA-OAEP', modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]),
      hash: 'SHA-256' },
    true, ['encrypt', 'decrypt']);
  return kp;
}

/** Exporte la clé publique en SPKI b64. */
async function vaultExportPublicKeyB64(publicKey) {
  const spki = await crypto.subtle.exportKey('spki', publicKey);
  return bufToB64(spki);
}

/** Chiffre (RSA-OAEP) les octets avec une clé publique importée depuis du SPKI b64. */
async function vaultRsaEncrypt(publicKeySpkiB64, dataBytes) {
  const pub = await crypto.subtle.importKey('spki', b64ToBuf(publicKeySpkiB64),
    { name: 'RSA-OAEP', hash: 'SHA-256' }, false, ['encrypt']);
  const ct = await crypto.subtle.encrypt({ name: 'RSA-OAEP' }, pub, dataBytes);
  return bufToB64(ct);
}

/** Déchiffre (RSA-OAEP) la b64 avec la clé publique CryptoKey. */
async function vaultRsaDecrypt(privateKey, ctb64) {
  const pt = await crypto.subtle.decrypt({ name: 'RSA-OAEP' }, privateKey, b64ToBuf(ctb64));
  return new Uint8Array(pt);
}

// ── HKDF (clé de métadonnées) ─────────────────────────────────

/**
 * Dérive une clé de méta AES-256 via HKDF-SHA256 depuis la clé de fichier.
 * info fixe liée au rôle pour distinguer le contexte d'usage.
 */
async function vaultDeriveMetaKey(fileKeyRawBytes) {
  const base = await crypto.subtle.importKey('raw', fileKeyRawBytes, 'HKDF', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits(
    { name: 'HKDF', hash: 'SHA-256',
      salt: new Uint8Array(0),            // pas de sel
      info: strToBuf('vault-metadata-v1') },
    base, 256);
  return new Uint8Array(bits);
}

// ── Enveloppe de clé privée ───────────────────────────────────

/** Exporte la clé privée en PKCS#8 puis chiffre avec la clé de compte.
 *  Retourne une string JSON {"ct": b64, "iv": hex} à envoyer au serveur. */
async function vaultWrapPrivateKey(privateKeyObj, accountKeyRawBytes) {
  const pkcs8 = await crypto.subtle.exportKey('pkcs8', privateKeyObj);
  const aesKey = await vaultImportAesKey(accountKeyRawBytes);
  const payload = await vaultAesEncryptBytes(aesKey, new Uint8Array(pkcs8));
  return JSON.stringify(payload);   // { iv, ct }
}

/** Déchiffre la clé privée stockée côté serveur avec la clé de compte (dans le navigateur).
 *  Retourne une CryptoKey RSA non exportable (extractible: false). */
async function vaultUnwrapPrivateKey(wrappedJson, accountKeyRawBytes) {
  const payload = (typeof wrappedJson === 'string') ? JSON.parse(wrappedJson) : wrappedJson;
  // Accepte les octets de la clé de compte ou une CryptoKey AES déjà importée
  const aesKey = (accountKeyRawBytes instanceof CryptoKey)
    ? accountKeyRawBytes : await vaultImportAesKey(accountKeyRawBytes);
  const pkcs8 = await vaultAesDecryptBytes(aesKey, payload);
  return crypto.subtle.importKey('pkcs8', pkcs8,
    { name: 'RSA-OAEP', hash: 'SHA-256' }, false, ['decrypt']);  // NOT extractible
}


// ── Récupération : dérivation à partir de la phrase BIP-39 ────

/**
 * Dérive 512 bits de la phrase mnémonique (PBKDF2-SHA256, 600 000 itérations,
 * sel = "vault-recovery:" + email) :
 * - recoveryKey (256 bits) : chiffre la copie de récupération de la clé privée ;
 * - recoveryAuth (256 bits) : preuve de possession de la phrase, envoyée au
 *   serveur qui la hache avec Argon2id (le serveur ne voit jamais la phrase).
 */
async function vaultDeriveRecovery(mnemonic, email) {
  const salt = strToBuf('vault-recovery:' + email.trim().toLowerCase());
  const base = await crypto.subtle.importKey('raw', strToBuf(mnemonic), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits(
    { name: 'PBKDF2', hash: 'SHA-256', salt, iterations: VAULT_PBKDF2_ITERATIONS }, base, 512);
  const raw = new Uint8Array(bits);
  return { recoveryKey: raw.slice(0, 32), recoveryAuth: raw.slice(32, 64) };
}

// ── Remplissage du contenu : algorithme Padmé (Nikitin et al., 2019) ──
// La taille stockée ne garde que les bits de poids fort de la taille réelle :
// pour une taille L, on ne conserve que ⌊log2 ⌊log2 L⌋⌋ + 1 bits significatifs.
// Le surcoût est au plus de 12 % et diminue quand la taille augmente.
// Un plancher de 4 Kio masque en plus la taille exacte des très petits fichiers.

const VAULT_PADDING_MIN = 4 * 1024;

function vaultGetPaddedSize(actualSize) {
  const L = Math.max(actualSize, VAULT_PADDING_MIN);
  const E = Math.floor(Math.log2(L));
  const S = Math.floor(Math.log2(E)) + 1;
  const step = Math.pow(2, E - S);               // arithmétique flottante : sûre au-delà de 2^31
  return Math.ceil(L / step) * step;
}

function vaultAddPadding(dataBytes, targetSize) {  // aléatoire (secrets.token_bytes ≈ CSPRNG)
  const out = new Uint8Array(targetSize);
  out.set(dataBytes, 0);
  // getRandomValues refuse plus de 65 536 octets par appel : on remplit par blocs
  const CHUNK = 65536;
  for (let off = dataBytes.length; off < targetSize; off += CHUNK) {
    crypto.getRandomValues(out.subarray(off, Math.min(off + CHUNK, targetSize)));
  }
  return out;
}

function vaultStripPadding(paddedBytes, originalSize) {
  return paddedBytes.slice(0, originalSize);
}

// ── Empreinte courte d'une clé publique (vérification à voix haute) ──
// SHA-256 de la clé (SPKI), 8 premiers octets en hexadécimal : « 7F3A 91C2 4B08 E5D1 ».
async function vaultKeyFingerprint(spkiB64) {
  const h = new Uint8Array(await crypto.subtle.digest('SHA-256', b64ToBuf(spkiB64)));
  return bufToHex(h.slice(0, 8)).toUpperCase().match(/.{4}/g).join(' ');
}

// ── SHA-256 (intégrité) ───────────────────────────────────────

async function vaultSha256Hex(bytes) {
  return bufToHex(await crypto.subtle.digest('SHA-256', bytes));
}

// ── Nombre aléatoire en hex (sel serveur demandé obsolete) ────

function vaultRandomHex(numBytes) {
  const b = crypto.getRandomValues(new Uint8Array(numBytes));
  return bufToHex(b);
}
