/**
 * Page « Copier » ouverte depuis un courriel. Le code ou le mot de passe est dans la
 * partie de l'adresse après « # » : le navigateur ne l'envoie jamais au serveur.
 * Adresse : /copier#c=123456 (code) ou /copier#p=MotDePasse (mot de passe temporaire).
 */
(function () {
  'use strict';
  const params = new URLSearchParams(window.location.hash.slice(1));
  const value = (params.get('c') || params.get('p') || '').replace(/[^A-Za-z0-9]/g, '').slice(0, 64);
  const isPw = params.has('p');
  // Le secret ne reste pas dans l'historique du navigateur
  history.replaceState(null, '', window.location.pathname);
  const box = document.getElementById('copyValue');
  const btn = document.getElementById('copyBtn');
  document.getElementById('copyTitle').textContent = isPw ? 'Votre mot de passe temporaire' : 'Votre code de vérification';
  if (!value) { box.textContent = '—'; btn.disabled = true; return; }
  box.textContent = value;

  async function copy() {
    let ok = false;
    try { await navigator.clipboard.writeText(value); ok = true; } catch (e) { /* ancienne méthode ci-dessous */ }
    if (!ok) {
      const t = document.createElement('textarea');
      t.value = value; t.setAttribute('readonly', ''); t.style.position = 'fixed'; t.style.opacity = '0';
      document.body.appendChild(t); t.select();
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      t.remove();
    }
    if (ok) { btn.textContent = 'Copié ✓'; btn.classList.add('done'); }
    else { btn.textContent = 'Sélectionnez puis copiez'; }
  }
  btn.addEventListener('click', copy);
})();
