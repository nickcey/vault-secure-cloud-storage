/**
 * vault-recovery.js — Récupération de compte par phrase mnémonique.
 * 100 % côté client : la phrase BIP-39 ne quitte jamais le navigateur.
 *   1. L'utilisateur saisit son e-mail, sa phrase (12 mots) et un nouveau mot de passe.
 *   2. Le navigateur dérive de la phrase la clé de récupération et une preuve
 *      de possession (recoveryAuth).
 *   3. Le serveur renvoie la copie de récupération chiffrée de la clé privée.
 *   4. Le navigateur la déchiffre et la rechiffre avec le nouveau mot de passe.
 *   5. Le serveur n'accepte le nouveau coffre que si la preuve de possession
 *      de la phrase est correcte (hachée en Argon2id côté serveur).
 */
(function () {
  'use strict';

  function showMsg(text, type) {
    const el = document.getElementById('recoverMsg');
    if (!el) return;
    el.textContent = text;
    el.className = 'flash ' + (type || 'info');
    el.style.display = 'block';
  }

  function csrfToken() {
    const m = document.querySelector('meta[name="csrf-token"]');
    return m ? m.getAttribute('content') : '';
  }

  async function postJson(url, obj) {
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken() },
      credentials: 'same-origin',
      body: JSON.stringify(obj),
    });
    return { ok: r.ok, data: await r.json().catch(() => ({})) };
  }

  const form = document.getElementById('recoverForm');
  if (!form) return;

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    const btn = form.querySelector('button[type="submit"]');
    const email = document.getElementById('email').value.trim().toLowerCase();
    const words = [];
    for (let i = 0; i < 12; i++) {
      const inp = document.getElementById('word_' + i);
      const w = inp ? inp.value.trim().toLowerCase() : '';
      if (!w) return showMsg('Saisissez les 12 mots.', 'error');
      words.push(w);
    }
    const mnemonic = VaultBip39.normalizeMnemonic(words.join(' '));
    const newPassword = document.getElementById('new_password').value;
    const confirmPw = document.getElementById('confirm_password').value;
    if (newPassword !== confirmPw) return showMsg('Les mots de passe diffèrent.', 'error');
    if (newPassword.length < 8) return showMsg('8 caractères minimum.', 'error');
    if (!(await VaultBip39.validateMnemonic(mnemonic))) {
      return showMsg('Phrase invalide : vérifiez l\'orthographe et l\'ordre des 12 mots.', 'error');
    }

    btn.disabled = true;
    try {
      showMsg('Vérification de la phrase...', 'info');
      const { recoveryKey, recoveryAuth } = await vaultDeriveRecovery(mnemonic, email);

      // 1. Copie de récupération chiffrée (le serveur ne peut pas la lire)
      const info = await postJson('/api/recovery-info', { email });
      if (!info.ok) { btn.disabled = false; return showMsg(info.data.error || 'Récupération impossible.', 'error'); }

      // 2. Déchiffrement local de la clé privée
      let pkcs8;
      try {
        pkcs8 = await vaultAesDecryptBytes(await vaultImportAesKey(recoveryKey),
                                           JSON.parse(info.data.recovery_wrapped_key));
      } catch (err) {
        btn.disabled = false;
        return showMsg('Phrase de récupération incorrecte pour ce compte.', 'error');
      }

      // 3. Nouveau mot de passe : nouveau sel, nouvelle clé de compte
      showMsg('Phrase valide. Protection de vos clés avec le nouveau mot de passe...', 'info');
      const newSalt = crypto.getRandomValues(new Uint8Array(16));
      const { accountKey: newKey, authValue: newAuth } = await vaultDeriveKeys(newPassword, newSalt);
      const newWrapped = JSON.stringify(await vaultAesEncryptBytes(await vaultImportAesKey(newKey), pkcs8));

      // 4. Envoi du nouveau coffre avec la preuve de possession de la phrase
      const cf = await postJson('/api/recover-confirm', {
        email,
        recovery_auth_value: bufToHex(recoveryAuth),
        auth_value: bufToHex(newAuth),
        salt: bufToHex(newSalt),
        encrypted_private_key: newWrapped,
      });
      if (!cf.ok) { btn.disabled = false; return showMsg(cf.data.error || 'Erreur', 'error'); }

      for (let i = 0; i < 12; i++) document.getElementById('word_' + i).value = '';
      showMsg('Mot de passe réinitialisé. Redirection vers la connexion...', 'success');
      setTimeout(() => { window.location.replace('/login'); }, 1500);
    } catch (err) {
      btn.disabled = false;
      showMsg('Erreur : ' + err.message, 'error');
    }
  });
})();
