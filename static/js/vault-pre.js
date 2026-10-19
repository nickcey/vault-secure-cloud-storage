/**
 * vault-pre.js — Partage entre utilisateurs par proxy re-encryption (Umbral).
 *
 * - Chaque compte possède une paire Umbral (re-chiffrement) et une paire de signature.
 *   Les clés secrètes sont chiffrées RSA-OAEP avec la clé publique du compte : seul
 *   le navigateur du titulaire, qui détient la clé privée RSA, peut les relire.
 * - Partager = envoyer au serveur un fragment de re-chiffrement (kfrag) signé.
 *   Le serveur transforme la capsule de la clé de fichier pour le destinataire,
 *   sans jamais pouvoir la déchiffrer lui-même.
 */
(function () {
  'use strict';

  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  async function api(url, opts = {}) {
    opts.credentials = 'same-origin';
    opts.headers = Object.assign({ 'X-CSRFToken': csrfMeta ? csrfMeta.getAttribute('content') : '' },
                                 opts.headers || {});
    if (opts.json !== undefined) {
      opts.method = opts.method || 'POST';
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(opts.json);
      delete opts.json;
    }
    const r = await fetch(url, opts);
    return { ok: r.ok, status: r.status, data: await r.json().catch(() => ({})) };
  }

  const toHex = b => Array.from(b, x => x.toString(16).padStart(2, '0')).join('');

  function getUmbral() {
    if (window.Umbral) return Promise.resolve(window.Umbral);
    return new Promise((resolve, reject) => {
      window.addEventListener('umbral-ready', () => resolve(window.Umbral), { once: true });
      setTimeout(() => { if (!window.Umbral) reject(new Error('Module Umbral non chargé')); }, 15000);
    });
  }

  let meCache = null;
  async function me(refresh) {
    if (!meCache || refresh) {
      const r = await api('/api/me');
      if (!r.ok) throw new Error('Session expirée');
      meCache = r.data;
    }
    return meCache;
  }

  /** Crée les clés Umbral du compte si elles n'existent pas encore. */
  async function ensureKeys() {
    const m = await me();
    if (m.umbral_public_key || !m.pre_available) return m;
    const U = await getUmbral();
    const sk = U.SecretKey.random();
    const signSk = U.SecretKey.random();
    const signer = new U.Signer(signSk);
    const secrets64 = new Uint8Array(64);
    secrets64.set(sk.toBEBytes(), 0);
    secrets64.set(signSk.toBEBytes(), 32);
    const enc = await vaultRsaEncrypt(m.public_key, secrets64);
    secrets64.fill(0);
    const r = await api('/api/umbral-keys', { json: {
      umbral_public_key: toHex(sk.publicKey().toCompressedBytes()),
      verifying_key: toHex(signer.verifyingKey().toCompressedBytes()),
      encrypted_umbral_keys: enc,
    } });
    if (!r.ok && r.status !== 400) throw new Error(r.data.error || 'Erreur');
    return me(true);
  }

  /** Clés secrètes Umbral, déchiffrées en mémoire avec la clé privée RSA du navigateur. */
  async function secrets() {
    const m = await ensureKeys();
    const privateKey = await VaultKeyStore.load();
    if (!privateKey) throw new Error('Clé privée expirée — reconnectez-vous.');
    const U = await getUmbral();
    const raw = await vaultRsaDecrypt(privateKey, m.encrypted_umbral_keys);
    const sk = U.SecretKey.fromBEBytes(raw.slice(0, 32));
    const signer = new U.Signer(U.SecretKey.fromBEBytes(raw.slice(32, 64)));
    raw.fill(0);
    return { U, me: m, sk, signer };
  }

  /** Empreinte courte des clés publiques de partage, à comparer de vive voix. */
  async function fingerprint(umbralPkHex, verifyingHex) {
    const data = hexToBuf(umbralPkHex + verifyingHex);
    const h = toHex(new Uint8Array(await crypto.subtle.digest('SHA-256', data))).toUpperCase();
    return h.slice(0, 20).match(/.{4}/g).join(' ');
  }

  async function lookup(email, opts) {
    const needUmbral = !(opts && opts.requireUmbral === false);
    const r = await api('/api/users/lookup', { json: { email } });
    if (!r.ok) throw new Error(r.data.error || 'Utilisateur introuvable');
    if (needUmbral && !r.data.umbral_public_key) {
      throw new Error("Cet utilisateur doit se connecter une première fois pour activer le partage.");
    }
    if (r.data.umbral_public_key) r.data.fingerprint = await fingerprint(r.data.umbral_public_key, r.data.verifying_key);
    return r.data;
  }

  /**
   * Partage un fichier avec un utilisateur Vault.
   * file : enregistrement de /api/files ; fileKeyBytes : clé du fichier (déjà déchiffrée).
   */
  async function shareWithUser(file, fileKeyBytes, recipient, opts) {
    const { U, me: m, sk, signer } = await secrets();
    const payload = { recipient_id: recipient.id };
    if (opts && Array.isArray(opts.folderPath) && recipient.public_key) {
      // Chemin du fichier dans le dossier partagé, lisible par le seul destinataire
      const k = crypto.getRandomValues(new Uint8Array(32));
      const enc = await vaultAesEncryptBytes(await vaultImportAesKey(k), strToBuf(JSON.stringify(opts.folderPath)));
      payload.folder_label = JSON.stringify({ k: await vaultRsaEncrypt(recipient.public_key, k), iv: enc.iv, ct: enc.ct });
      k.fill(0);
    }
    if (!file.has_capsule) {
      // Capsule : la clé de fichier chiffrée pour SA PROPRE clé publique Umbral
      const [capsule, ct] = U.encrypt(U.PublicKey.fromCompressedBytes(hexToBuf(m.umbral_public_key)),
                                      fileKeyBytes);
      payload.capsule = bufToB64(capsule.toBytes());
      payload.umbral_ciphertext = bufToB64(ct);
    }
    if (!recipient.has_delegation) {
      // Fragment de re-chiffrement propriétaire -> destinataire, seuil 1 sur 1, signé
      const kfrags = U.generateKFrags(sk, U.PublicKey.fromCompressedBytes(hexToBuf(recipient.umbral_public_key)),
                                      signer, 1, 1, true, true);
      payload.kfrag = bufToB64(kfrags[0].toBytes());
    }
    const r = await api('/api/files/' + file.id + '/share-user', { json: payload });
    if (!r.ok) throw new Error(r.data.error || 'Partage refusé');
    return true;
  }

  /** Destinataire : chemin du fichier dans le dossier partagé (null si partagé seul). */
  async function openLabel(item, privateKey) {
    if (!item.folder_label) return null;
    try {
      const l = JSON.parse(item.folder_label);
      const k = await vaultRsaDecrypt(privateKey, l.k);
      const path = JSON.parse(bufToStr(await vaultAesDecryptBytes(await vaultImportAesKey(k), { iv: l.iv, ct: l.ct })));
      return Array.isArray(path) && path.length ? path.map(String) : null;
    } catch (e) { return null; }
  }

  /** Destinataire : retrouve la clé de fichier à partir du fragment re-chiffré par le serveur. */
  async function openShared(item) {
    const { U, me: m, sk } = await secrets();
    const pk = h => U.PublicKey.fromCompressedBytes(hexToBuf(h));
    const capsule = U.Capsule.fromBytes(b64ToBuf(item.capsule));
    // Vérifie que le re-chiffrement est correct ET autorisé par la signature du propriétaire
    const vcfrag = U.CapsuleFrag.fromBytes(b64ToBuf(item.cfrag))
      .verify(capsule, pk(item.owner.verifying_key), pk(item.owner.umbral_public_key), pk(m.umbral_public_key));
    return U.decryptReencrypted(sk, pk(item.owner.umbral_public_key), capsule, [vcfrag],
                                b64ToBuf(item.umbral_ciphertext));
  }

  window.VaultPRE = { getUmbral, ensureKeys, fingerprint, lookup, shareWithUser, openShared, openLabel, me, api };
})();
