/**
 * vault-share-list.js — Liens de partage de l'utilisateur.
 * Le nom du fichier et le lien complet (clé dans le fragment #) sont
 * reconstitués dans le navigateur : seul le propriétaire peut le faire.
 */
(function () {
  'use strict';

  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  async function api(url, opts = {}) {
    opts.credentials = 'same-origin';
    opts.headers = Object.assign({}, opts.headers, {
      'X-CSRFToken': csrfMeta ? csrfMeta.getAttribute('content') : '',
    });
    const r = await fetch(url, opts);
    return { ok: r.ok, data: await r.json().catch(() => ({})) };
  }

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  const host = document.getElementById('shareList');
  if (!host) return;
  const LINK_SVG = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>';

  async function buildRow(l, privateKey) {
    let name = 'Fichier', url = null;
    if (l.encrypted_file_key) {
      try {
        const fileKeyRaw = await vaultRsaDecrypt(privateKey, l.encrypted_file_key);
        const metaKey = await vaultImportAesKey(await vaultDeriveMetaKey(fileKeyRaw));
        const raw = b64ToBuf(l.encrypted_metadata);
        const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: raw.slice(0, 12) }, metaKey, raw.slice(12));
        name = JSON.parse(bufToStr(new Uint8Array(pt))).filename || name;
        const frag = bufToB64(fileKeyRaw).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
        url = window.location.origin + '/share-download/' + l.token + '#' + frag;
      } catch (e) { /* fichier illisible : on affiche quand même le lien pour le révoquer */ }
    }

    const row = el('div', 'link-row');
    const icon = el('div', 'link-icon'); icon.innerHTML = LINK_SVG;
    const info = el('div', 'link-info');
    info.appendChild(el('div', 'link-label', name));
    const meta = el('div', 'link-meta');
    meta.append(el('span', '', '⏰ Expire le ' + l.expires_at),
      el('span', '', '⬇ ' + l.download_count + (l.max_downloads > 0 ? '/' + l.max_downloads : '') + ' téléchargement(s)'));
    info.appendChild(meta);

    const actions = el('div', 'link-actions');
    if (url) {
      const copy = el('button', 'btn-copy', 'Copier le lien'); copy.type = 'button';
      copy.addEventListener('click', async () => {
        try { await navigator.clipboard.writeText(url); copy.textContent = 'Copié ✓'; }
        catch (e) { window.prompt('Lien de partage :', url); }
        setTimeout(() => { copy.textContent = 'Copier le lien'; }, 1800);
      });
      actions.appendChild(copy);
    }
    const rv = el('button', 'btn-revoke', 'Révoquer'); rv.type = 'button';
    rv.addEventListener('click', async () => {
      if (!window.confirm('Révoquer ce lien ?')) return;
      await api('/api/share/revoke/' + l.id, { method: 'POST' });
      load();
    });
    actions.appendChild(rv);
    row.append(icon, info, actions);
    return row;
  }

  async function load() {
    const empty = document.getElementById('shareEmpty');
    const privateKey = await VaultKeyStore.load();
    if (!privateKey) {
      host.innerHTML = '';
      host.appendChild(el('div', 'empty-state', 'Clé privée expirée — reconnectez-vous.'));
      return;
    }
    const links = await api('/api/share/list');
    if (!links.ok) return;
    const rows = [];
    for (const l of links.data.links) rows.push(await buildRow(l, privateKey));
    host.innerHTML = '';
    rows.forEach(r => host.appendChild(r));
    if (empty) empty.style.display = rows.length ? 'none' : '';
  }

  load();
})();
