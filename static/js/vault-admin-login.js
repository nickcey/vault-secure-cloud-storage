/**
 * vault-admin-login.js — Connexion administrateur.
 * Comme pour les utilisateurs, le mot de passe ne quitte pas le navigateur :
 * seule la valeur d'authentification dérivée (PBKDF2) est envoyée.
 */
(function () {
  'use strict';
  const form = document.getElementById('adminLoginForm');
  if (!form) return;
  const csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content ||
               ((document.querySelector('input[name="csrf_token"]') || {}).value || '');

  function msg(text) {
    const el = document.getElementById('adminMsg');
    if (!el) return alert(text);
    el.textContent = text;
    el.className = 'flash error';
    el.style.display = 'block';
  }

  async function post(url, obj) {
    const r = await fetch(url, {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
      body: JSON.stringify(obj),
    });
    return { ok: r.ok, data: await r.json().catch(() => ({})) };
  }

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    const btn = document.getElementById('loginBtn');
    btn.disabled = true;
    btn.textContent = 'Vérification...';
    try {
      const email = document.getElementById('email').value.trim().toLowerCase();
      const password = document.getElementById('password').value;
      const salt = await post('/admin/get-salt', { email });
      const { authValue } = await vaultDeriveKeys(password, hexToBuf(salt.data.salt));
      const r = await post('/admin/login', { email, auth_value: bufToHex(authValue) });
      if (!r.ok) throw new Error(r.data.error || 'Identifiants incorrects.');
      window.location.replace(r.data.redirect || '/admin');
    } catch (err) {
      msg(err.message);
      btn.disabled = false;
      btn.textContent = 'Accéder au panneau';
    }
  });
})();
