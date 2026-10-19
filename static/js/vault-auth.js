/**
 * vault-auth.js — Connexion / code de vérification / premier mot de passe /
 * changement de mot de passe.
 * Le mot de passe ne quitte JAMAIS le navigateur : seuls la valeur
 * d'authentification dérivée et l'enveloppe chiffrée de la clé privée
 * sont envoyées au serveur.
 */
(function () {
  'use strict';

  function csrfToken() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : '';
  }

  async function postJson(url, obj) {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
      credentials: 'same-origin',
      body: JSON.stringify(obj || {}),
    });
    return { ok: resp.ok, status: resp.status, data: await resp.json().catch(() => ({})) };
  }

  function showMsg(id, text, type) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text;
    el.className = 'flash ' + (type || 'info');
    el.style.display = 'block';
  }

  function setBusy(btn, busy) {
    if (!btn) return;
    btn.disabled = !!busy;
    btn.classList.toggle('btn-loader', !!busy);
  }

  // ═══════════════ CONNEXION (étape 1 : mot de passe) ═══════════════

  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    // Toute clé restée d'une session précédente est effacée
    if (window.VaultKeyStore) VaultKeyStore.clear().catch(() => {});

    loginForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      const btn = document.getElementById('loginSubmitBtn');
      const email = document.getElementById('email').value.trim().toLowerCase();
      const password = document.getElementById('password').value;
      if (!email || !password) return showMsg('loginMsg', 'Saisissez votre email et votre mot de passe.', 'error');
      setBusy(btn, true);
      try {
        // 1. Sel public du compte
        const saltResp = await postJson('/get-salt', { email });
        if (!saltResp.ok) throw new Error(saltResp.data.error || 'Erreur');
        // 2. Dérivation locale : clé de compte (reste ici) + valeur d'authentification
        const { accountKey, authValue } = await vaultDeriveKeys(password, hexToBuf(saltResp.data.salt));
        // 3. Seule la valeur d'authentification part au serveur
        const r = await postJson('/login', { email, auth_value: bufToHex(authValue) });
        if (!r.ok) { setBusy(btn, false); return showMsg('loginMsg', r.data.error || 'Erreur de connexion', 'error'); }
        // 4. La clé de compte attend la page du code, non exportable
        await VaultKeyStore.savePending(await vaultImportAesKey(accountKey));
        window.location.replace(r.data.next || '/verify-otp');
      } catch (err) {
        setBusy(btn, false);
        showMsg('loginMsg', 'Erreur : ' + err.message, 'error');
      }
    });
  }

  // ═══════════════ CONNEXION (étape 2 : code reçu par email) ═══════════════

  const otpForm = document.getElementById('otpForm');
  if (otpForm && otpForm.dataset.zk === '1') {
    otpForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      const btn = otpForm.querySelector('button[type="submit"]');
      const code = document.getElementById('otp_code').value.trim();
      if (!/^\d{6}$/.test(code)) { setBusy(btn, false); return showMsg('otpMsg', 'Code à 6 chiffres requis.', 'error'); }
      setBusy(btn, true);
      const rv = await postJson('/verify-otp', { otp_code: code });
      if (!rv.ok) {
        setBusy(btn, false);
        showMsg('otpMsg', rv.data.error || 'Code invalide', 'error');
        if (rv.data.restart) setTimeout(() => { window.location.replace('/login'); }, 1800);
        return;
      }
      const pending = await VaultKeyStore.takePending();
      if (rv.data.must_change_password) {
        window.location.replace('/change-password');
        return;
      }
      if (!pending) {
        setBusy(btn, false);
        showMsg('otpMsg', 'Session expirée dans ce navigateur. Reconnectez-vous.', 'error');
        setTimeout(() => { window.location.replace('/logout'); }, 2000);
        return;
      }
      try {
        // Déchiffrement de la clé privée dans le navigateur ; CryptoKey non exportable
        const privateKey = await vaultUnwrapPrivateKey(rv.data.encrypted_private_key, pending);
        await VaultKeyStore.save(privateKey);
        window.location.replace('/dashboard');
      } catch (err) {
        setBusy(btn, false);
        showMsg('otpMsg', 'Échec du déchiffrement de la clé privée : ' + err.message, 'error');
      }
    });

    const resendForm = document.getElementById('resendForm');
    if (resendForm) {
      resendForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        const r = await postJson('/verify-otp', { action: 'resend' });
        if (r.ok) { window.location.reload(); return; }
        const b = resendForm.querySelector('button');
        setBusy(b, false);
        showMsg('otpMsg', r.data.error || 'Erreur', 'error');
        if (r.data.restart) setTimeout(() => { window.location.replace('/login'); }, 1800);
      });
    }
  }

  // ═══════════════ MOT DE PASSE (premier choix ou changement) ═══════════════

  const changeForm = document.getElementById('changePasswordForm');
  if (changeForm) {
    const isFirst = document.body.dataset.temp === '1';

    changeForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      const btn = changeForm.querySelector('button[type="submit"]');
      const current = document.getElementById('old_password').value;
      const newPw = document.getElementById('new_password').value;
      const confirmPw = document.getElementById('confirm_password').value;
      if (newPw !== confirmPw) return showMsg('msg', 'Les mots de passe ne correspondent pas.', 'error');
      if (newPw.length < 8) return showMsg('msg', 'Le mot de passe doit contenir au moins 8 caractères.', 'error');

      const email = (document.body.dataset.email || '').trim().toLowerCase();
      if (!email) return showMsg('msg', 'Session invalide, reconnectez-vous.', 'error');
      setBusy(btn, true);

      try {
        const saltResp = await postJson('/get-salt', { email });
        const { accountKey: currentKey, authValue: currentAuth } =
          await vaultDeriveKeys(current, hexToBuf(saltResp.data.salt));
        const newSalt = crypto.getRandomValues(new Uint8Array(16));
        const { accountKey: newKey, authValue: newAuth } = await vaultDeriveKeys(newPw, newSalt);

        if (isFirst) {
          // ── Premier mot de passe : création des clés ICI, dans le navigateur ──
          showMsg('msg', 'Création de vos clés de chiffrement (quelques secondes)...', 'info');
          const kp = await vaultGenerateKeyPair();
          const pubkeyB64 = await vaultExportPublicKeyB64(kp.publicKey);
          const wrappedPk = await vaultWrapPrivateKey(kp.privateKey, newKey);
          // Phrase de récupération BIP-39 (générée ici, jamais envoyée)
          const mnemonic = await VaultBip39.generateMnemonic();
          const { recoveryKey, recoveryAuth } = await vaultDeriveRecovery(mnemonic, email);
          const recoveryWrappedPk = await vaultWrapPrivateKey(kp.privateKey, recoveryKey);

          const r = await postJson('/api/setup-keys', {
            current_auth_value: bufToHex(currentAuth),
            auth_value: bufToHex(newAuth),
            recovery_auth_value: bufToHex(recoveryAuth),
            salt: bufToHex(newSalt),
            public_key: pubkeyB64,
            encrypted_private_key: wrappedPk,
            recovery_wrapped_key: recoveryWrappedPk,
          });
          if (!r.ok) { setBusy(btn, false); return showMsg('msg', r.data.error || 'Erreur', 'error'); }

          await VaultKeyStore.save(await vaultUnwrapPrivateKey(wrappedPk, newKey));
          showMnemonic(mnemonic);
          return;
        }

        // ── Changement normal : la clé privée est rechiffrée avec le nouveau mot de passe ──
        const privateKey = await VaultKeyStore.load();
        if (!privateKey) { setBusy(btn, false); return showMsg('msg', 'Clé privée expirée. Déconnectez-vous puis reconnectez-vous.', 'error'); }
        showMsg('msg', 'Calcul des nouvelles clés...', 'info');
        const me = await fetch('/api/me', { credentials: 'same-origin' }).then(x => x.json());
        const pkcs8 = await vaultAesDecryptBytes(await vaultImportAesKey(currentKey), JSON.parse(me.encrypted_private_key));
        const newWrapped = JSON.stringify(await vaultAesEncryptBytes(await vaultImportAesKey(newKey), pkcs8));
        const r = await postJson('/api/change-password', {
          current_auth_value: bufToHex(currentAuth),
          auth_value: bufToHex(newAuth),
          salt: bufToHex(newSalt),
          encrypted_private_key: newWrapped,
        });
        setBusy(btn, false);
        if (r.ok) {
          showMsg('msg', 'Mot de passe changé avec succès !', 'success');
          changeForm.reset();
        } else {
          showMsg('msg', r.data.error || 'Erreur', 'error');
        }
      } catch (err) {
        setBusy(btn, false);
        showMsg('msg', 'Mot de passe actuel incorrect ou erreur : ' + err.message, 'error');
      }
    });
  }

  // Affichage UNIQUE de la phrase de récupération (design de la page « phrase mnémonique »)
  function showMnemonic(mnemonic) {
    const formBox = document.getElementById('passwordStep');
    const box = document.getElementById('mnemonicSection');
    const words = document.getElementById('mnemonicBox');
    if (formBox) formBox.style.display = 'none';
    const title = document.getElementById('pwTitle');
    if (title) title.style.display = 'none';
    const msg = document.getElementById('msg');
    if (msg) msg.style.display = 'none';
    words.textContent = mnemonic;
    box.style.display = 'block';

    const copyBtn = document.getElementById('copyMnemonicBtn');
    if (copyBtn) {
      copyBtn.addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(mnemonic);
          const ok = document.getElementById('copiedMsg');
          if (ok) { ok.style.display = 'block'; setTimeout(() => { ok.style.display = 'none'; }, 2500); }
        } catch (e) { /* presse-papiers indisponible : l'utilisateur recopie à la main */ }
      });
    }
    document.getElementById('mnemonicDoneBtn').addEventListener('click', () => {
      words.textContent = '';
      window.location.replace('/dashboard');
    });
  }
})();
