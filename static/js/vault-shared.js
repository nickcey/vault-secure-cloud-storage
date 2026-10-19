/**
 * vault-shared.js — « Partagés avec moi » (destinataire) et partages accordés
 * à d'autres utilisateurs (propriétaire, page des liens).
 */
(function () {
  'use strict';

  function fmtSize(bytes) {
    if (bytes < 1024) return bytes + ' o';
    const units = ['Ko', 'Mo', 'Go', 'To'];
    let v = bytes, i = -1;
    do { v /= 1024; i++; } while (v >= 1024 && i < units.length - 1);
    return v.toFixed(i === 0 ? 0 : 1) + ' ' + units[i];
  }
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  async function decryptMeta(fileKeyBytes, encMetaB64) {
    const metaKey = await vaultImportAesKey(await vaultDeriveMetaKey(fileKeyBytes));
    const raw = b64ToBuf(encMetaB64);
    const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: raw.slice(0, 12) }, metaKey, raw.slice(12));
    return JSON.parse(bufToStr(new Uint8Array(pt)));
  }
  function saveFile(content, meta) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([content], { type: meta.mime_type || 'application/octet-stream' }));
    a.download = meta.filename || 'fichier';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10000);
  }

  // ═══════════ Destinataire : fichiers partagés avec moi ═══════════
  const host = document.getElementById('sharedWithMeList');
  if (host) {
    const empty = document.getElementById('sharedEmpty');
    const msg = document.getElementById('sharedMsg');
    const fail = t => { msg.textContent = t; msg.style.display = 'block'; };

    (async function load() {
      if (!(await VaultKeyStore.load())) return fail('Clé privée expirée — reconnectez-vous.');
      const r = await VaultPRE.api('/api/shared-with-me');
      if (!r.ok) return fail(r.data.error || 'Erreur');
      host.innerHTML = '';
      const pk = await VaultKeyStore.load();
      const opened = [];
      for (const item of r.data.files) {
        let fileKey, meta;
        try {
          fileKey = await VaultPRE.openShared(item);          // re-chiffrement vérifié + déchiffré ici
          meta = await decryptMeta(fileKey, item.encrypted_metadata);
        } catch (e) {
          meta = { filename: 'Fichier illisible (partage invalide)', plaintext_size: 0 };
          fileKey = null;
        }
        opened.push({ item, fileKey, meta, path: await VaultPRE.openLabel(item, pk) });
      }

      function fileRow({ item, fileKey, meta }, inFolder) {
        const row = el('div', 'file-row');
        const content = el('div', 'file-row-content');
        content.appendChild(window.vaultIconElement ? vaultIconElement(meta.filename) : el('div', 'file-icon'));
        const info = el('div', 'file-info');
        info.append(el('div', 'file-name', meta.filename),
          el('div', 'file-meta', fmtSize(meta.plaintext_size || 0) +
             (inFolder ? '' : ' · partagé par ' + item.owner.username + ' (' + item.owner.email + ')') +
             ' · le ' + item.shared_at));
        content.appendChild(info);
        const btn = el('button', 'btn btn-restore', '⬇ Télécharger'); btn.type = 'button';
        btn.disabled = !fileKey;
        btn.addEventListener('click', async () => {
          btn.disabled = true; btn.textContent = 'Déchiffrement...';
          try {
            const resp = await fetch('/api/shared-with-me/' + item.share_id + '/blob', { credentials: 'same-origin' });
            if (!resp.ok) throw new Error((await resp.json().catch(() => ({}))).error || 'Téléchargement refusé');
            const raw = new Uint8Array(await resp.arrayBuffer());
            const key = await vaultImportAesKey(fileKey);
            const padded = new Uint8Array(await crypto.subtle.decrypt({ name: 'AES-GCM', iv: raw.slice(0, 12) }, key, raw.slice(12)));
            const data = vaultStripPadding(padded, meta.plaintext_size);
            const expected = meta.content_sha256 || item.content_sha256;
            if (expected && (await vaultSha256Hex(data)) !== expected) {
              throw new Error('Intégrité du fichier compromise');
            }
            saveFile(data, meta);
            btn.textContent = '✅ Téléchargé';
          } catch (e) { fail('Erreur : ' + e.message); btn.textContent = '⬇ Télécharger'; }
          btn.disabled = false;
        });
        const group = el('div', 'btn-group'); group.appendChild(btn);
        row.append(content, group);
        return row;
      }

      // Fichiers partagés seuls, puis dossiers partagés (chemin déchiffré ici)
      opened.filter(o => !o.path).forEach(o => host.appendChild(fileRow(o, false)));
      const groups = new Map();
      opened.filter(o => o.path).forEach(o => {
        const key = o.item.owner.email + '\u0000' + o.path.join('\u0000');
        if (!groups.has(key)) groups.set(key, { owner: o.item.owner, path: o.path, files: [] });
        groups.get(key).files.push(o);
      });
      [...groups.values()]
        .sort((x, y) => (x.owner.username + x.path.join('/')).localeCompare(y.owner.username + y.path.join('/'), 'fr'))
        .forEach(g => {
          const box = el('div', 'folder-group');
          const head = el('div', 'folder-head');
          const txt = el('div');
          txt.append(el('div', 'fh-name', g.path.join(' › ')),
                     el('div', 'fh-meta', 'Dossier partagé par ' + g.owner.username + ' (' + g.owner.email + ') · ' +
                        g.files.length + ' fichier' + (g.files.length > 1 ? 's' : '')));
          head.append(el('span', 'fh-icon', '📁'), txt, el('span', 'fh-caret', '▾'));
          head.addEventListener('click', () => box.classList.toggle('closed'));
          const list = el('div', 'folder-files');
          g.files.sort((a, b) => (a.meta.filename || '').localeCompare(b.meta.filename || '', 'fr'))
            .forEach(o => list.appendChild(fileRow(o, true)));
          box.append(head, list);
          host.appendChild(box);
        });
      if (empty) empty.style.display = r.data.files.length ? 'none' : '';
    })().catch(e => fail('Erreur : ' + e.message));
  }

  // ═══════════ Propriétaire : partages accordés à des utilisateurs ═══════════
  const mine = document.getElementById('userSharesList');
  if (mine) {
    const emptyMine = document.getElementById('userSharesEmpty');
    (async function loadMine() {
      const privateKey = await VaultKeyStore.load();
      if (!privateKey) { mine.textContent = 'Clé privée expirée — reconnectez-vous.'; return; }
      const r = await VaultPRE.api('/api/my-user-shares');
      if (!r.ok) return;
      mine.innerHTML = '';
      for (const s of r.data.shares) {
        let name = 'Fichier';
        try {
          const fk = await vaultRsaDecrypt(privateKey, s.encrypted_file_key);
          name = (await decryptMeta(fk, s.encrypted_metadata)).filename || name;
        } catch (e) { /* nom illisible */ }
        const row = el('div', 'link-row');
        const icon = el('div', 'link-icon', '👤');
        const info = el('div', 'link-info');
        info.appendChild(el('div', 'link-label', name));
        const meta = el('div', 'link-meta');
        meta.append(el('span', '', '👤 ' + s.recipient.username + ' (' + s.recipient.email + ')'),
                    el('span', '', '📅 Partagé le ' + s.shared_at));
        info.appendChild(meta);
        const actions = el('div', 'link-actions');
        const rv = el('button', 'btn-revoke', 'Révoquer'); rv.type = 'button';
        rv.addEventListener('click', async () => {
          if (!window.confirm('Révoquer ce partage ? Le serveur ne pourra plus re-chiffrer ce fichier pour ' + s.recipient.username + '.')) return;
          await VaultPRE.api('/api/user-shares/' + s.share_id + '/revoke', { json: {} });
          loadMine();
        });
        actions.appendChild(rv);
        row.append(icon, info, actions);
        mine.appendChild(row);
      }
      if (emptyMine) emptyMine.style.display = r.data.shares.length ? 'none' : '';
    })();
  }

  // ═══════════ Paramètres : empreinte de mes clés de partage ═══════════
  const fpEl = document.getElementById('myFingerprint');
  if (fpEl) {
    VaultPRE.ensureKeys()
      .then(m => m.umbral_public_key ? VaultPRE.fingerprint(m.umbral_public_key, m.verifying_key) : '—')
      .then(fp => { fpEl.textContent = fp; })
      .catch(() => { fpEl.textContent = 'Reconnectez-vous pour l’afficher'; });
  }
})();
