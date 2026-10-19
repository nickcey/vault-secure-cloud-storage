/**
 * vault-recover-contacts.js — Récupération du compte par contacts de confiance.
 * 1. Code reçu par email ; 2. le navigateur crée une paire RSA temporaire (clé privée
 * non exportable, gardée dans IndexedDB) ; 3. les contacts rechiffrent leur part pour
 * cette clé ; 4. avec deux validations sur trois, le navigateur reconstitue la clé de récupération,
 * déchiffre la copie de la clé privée et la protège avec le nouveau mot de passe.
 */
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  async function post(url, obj) {
    const r = await fetch(url, { method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(obj || {}) });
    return { ok: r.ok, data: await r.json().catch(() => ({})) };
  }
  function msg(text, type) {
    const e = $('rcMsg'); e.textContent = text; e.className = 'flash ' + (type || 'info'); e.style.display = 'block';
  }
  function show(step) {
    ['rcStepEmail', 'rcStepCode', 'rcStepWait'].forEach(id => { $(id).style.display = id === step ? '' : 'none'; });
  }

  // ── Stockage local de la demande en cours (clé privée temporaire non exportable) ──
  const DB = 'vault-recovery-request', ST = 'req';
  function db() {
    return new Promise((res, rej) => {
      const q = indexedDB.open(DB, 1);
      q.onupgradeneeded = e => e.target.result.createObjectStore(ST);
      q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error);
    });
  }
  async function saveReq(v) { const d = await db(); return new Promise(r => { const t = d.transaction(ST, 'readwrite'); t.objectStore(ST).put(v, 'current'); t.oncomplete = r; }); }
  async function loadReq() { const d = await db(); return new Promise(r => { const q = d.transaction(ST).objectStore(ST).get('current'); q.onsuccess = () => r(q.result || null); q.onerror = () => r(null); }); }
  async function clearReq() { const d = await db(); return new Promise(r => { const t = d.transaction(ST, 'readwrite'); t.objectStore(ST).delete('current'); t.oncomplete = r; }); }

  let current = null, status = null;

  $('rcEmailForm').addEventListener('submit', async e => {
    e.preventDefault();
    const email = $('rcEmail').value.trim().toLowerCase();
    const r = await post('/api/shamir-recovery/start', { email });
    if (!r.ok) return msg(r.data.error || 'Erreur', 'error');
    msg(r.data.message + (r.data.dev_otp ? ' (Erreur envoi email. Code : ' + r.data.dev_otp + ')' : ''), 'info');
    $('rcEmailHold').value = email;
    show('rcStepCode');
  });

  $('rcCodeForm').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]'); btn.disabled = true;
    try {
      const kp = await crypto.subtle.generateKey({ name: 'RSA-OAEP', modulusLength: 2048,
        publicExponent: new Uint8Array([1, 0, 1]), hash: 'SHA-256' }, false, ['encrypt', 'decrypt']);
      const pub = await vaultExportPublicKeyB64(kp.publicKey);
      const r = await post('/api/shamir-recovery/verify', { otp_code: $('rcCode').value.trim(), temp_public_key: pub });
      if (!r.ok) throw new Error(r.data.error || 'Code invalide');
      current = { token: r.data.token, privateKey: kp.privateKey, publicKey: pub,
                  email: $('rcEmailHold').value, contacts: r.data.contacts };
      await saveReq(current);
      $('rcMsg').style.display = 'none';
      await refresh();
    } catch (err) { msg(err.message, 'error'); }
    btn.disabled = false;
  });

  async function collectParts() {
    const parts = [];
    for (const a of (status ? status.approvals : [])) {
      try {
        const y = await vaultRsaDecrypt(current.privateKey, a.encrypted_share);
        parts.push({ x: a.share_index, y });
      } catch (err) { /* part illisible : ignorée */ }
    }
    return parts;
  }

  // Toutes les combinaisons de k éléments (pour écarter une part falsifiée)
  function combos(arr, k, start = 0, acc = [], out = []) {
    if (acc.length === k) { out.push(acc.slice()); return out; }
    for (let i = start; i < arr.length; i++) { acc.push(arr[i]); combos(arr, k, i + 1, acc, out); acc.pop(); }
    return out;
  }

  async function refresh() {
    show('rcStepWait');
    const r = await post('/api/shamir-recovery/status', { token: current.token });
    if (!r.ok) { await clearReq(); show('rcStepEmail'); return msg(r.data.error || 'Demande expirée', 'error'); }
    status = r.data;
    $('rcWaitEmail').textContent = status.email;
    // Empreinte calculée ICI, à partir de la clé créée par ce navigateur : le contact
    // doit lire la même au téléphone, sinon la clé a été remplacée en chemin.
    if (current.publicKey) {
      $('rcFp').textContent = await vaultKeyFingerprint(current.publicKey);
      $('rcFpBox').style.display = '';
    }
    const list = $('rcApprovals'); list.innerHTML = '';
    (current.contacts || []).forEach(name => {
      const ok = status.approvals.some(a => a.contact === name);
      const li = document.createElement('li');
      li.textContent = (ok ? '✅ ' : '⏳ ') + name + (ok ? ' a validé' : ' n’a pas encore validé');
      list.appendChild(li);
    });
    updateReady();
  }

  function updateReady() {
    const k = (status && status.threshold) || 2;
    const n = status ? status.approvals.length : 0;
    $('rcCount').textContent = Math.min(n, k);
    $('rcNeed').textContent = k;
    $('rcFinalForm').style.display = n >= k ? '' : 'none';
  }
  $('rcRefresh').addEventListener('click', () => refresh());
  $('rcCancel').addEventListener('click', async () => { await clearReq(); location.reload(); });

  $('rcFinalForm').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = e.target.querySelector('button[type="submit"]'); btn.disabled = true;
    try {
      const pw = $('rcNewPw').value, pw2 = $('rcNewPw2').value;
      if (pw.length < 8) throw new Error('8 caractères minimum.');
      if (pw !== pw2) throw new Error('Les mots de passe ne correspondent pas.');
      msg('Reconstitution de la clé de récupération...', 'info');
      const parts = await collectParts();
      const k = status.threshold || 2;
      if (parts.length < k) throw new Error(k + ' validations sont nécessaires.');
      // Essaie chaque groupe de k parts : une part fausse est écartée, car seule
      // la bonne clé déchiffre la copie (tag AES-GCM).
      let pkcs8 = null, auth = null;
      for (const group of combos(parts, k)) {
        const S = VaultShamir.combine(group);
        const d = await VaultShamir.deriveFromSecret(S);
        S.fill(0);
        try {
          pkcs8 = await vaultAesDecryptBytes(await vaultImportAesKey(d.key), JSON.parse(status.shamir_wrapped_key));
          auth = d.auth;
          break;
        } catch (err) { /* groupe invalide, on essaie le suivant */ }
      }
      if (!pkcs8) throw new Error('Les parts reçues ne permettent pas de reconstituer la clé.');
      const salt = crypto.getRandomValues(new Uint8Array(16));
      const { accountKey, authValue } = await vaultDeriveKeys(pw, salt);
      const wrapped = JSON.stringify(await vaultAesEncryptBytes(await vaultImportAesKey(accountKey), pkcs8));
      pkcs8.fill(0);
      const r = await post('/api/shamir-recovery/complete', { token: current.token,
        shamir_auth_value: bufToHex(auth), auth_value: bufToHex(authValue),
        salt: bufToHex(salt), encrypted_private_key: wrapped });
      if (!r.ok) throw new Error(r.data.error || 'Erreur');
      await clearReq();
      msg('Compte récupéré ! Redirection vers la connexion...', 'success');
      setTimeout(() => { location.replace('/login'); }, 1800);
    } catch (err) { msg(err.message, 'error'); btn.disabled = false; }
  });

  (async function init() {
    current = await loadReq();
    if (current) refresh(); else show('rcStepEmail');
  })();
})();
