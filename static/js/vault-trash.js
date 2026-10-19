/**
 * vault-trash.js — Corbeille : noms déchiffrés dans le navigateur.
 * Le rendu reprend le design de la page ; la fenêtre de confirmation est
 * fournie par la page via window.VaultTrashUI.confirm(kind, onConfirm).
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

  const list = document.getElementById('trashList');
  if (!list) return;
  const L = Object.assign({ restore: 'Restaurer', delete_permanently: 'Supprimer définitivement',
    expired: 'Expiré', deleted_on: 'Supprimé le', expires: 'Expire le',
    key_expired: 'Clé privée expirée — reconnectez-vous.' }, window.VAULT_I18N || {});

  const fileKeys = {};   // clé de fichier par uuid, en mémoire seulement
  let privateKey = null;

  async function decryptMeta(f) {
    try {
      if (!fileKeys[f.uuid]) fileKeys[f.uuid] = await vaultRsaDecrypt(privateKey, f.encrypted_file_key);
      const metaKey = await vaultImportAesKey(await vaultDeriveMetaKey(fileKeys[f.uuid]));
      const raw = b64ToBuf(f.encrypted_metadata);
      const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: raw.slice(0, 12) }, metaKey, raw.slice(12));
      return JSON.parse(bufToStr(new Uint8Array(pt)));
    } catch (e) {
      return { filename: 'fichier-illisible-' + String(f.uuid).slice(0, 8), plaintext_size: 0 };
    }
  }

  function ask(kind, action) {
    const ui = window.VaultTrashUI;
    if (ui && ui.confirm) ui.confirm(kind, action);
    else if (window.confirm(kind === 'restore' ? L.restore + ' ?' : L.delete_permanently + ' ?')) action();
  }

  function buildRow(f, meta) {
    const name = meta.filename || 'fichier';
    const ext = (window.vaultFileIcon ? window.vaultFileIcon(name).ext : '') || '';
    const row = el('div', 'file-row');
    const content = el('div', 'file-row-content');
    content.appendChild(window.vaultIconElement ? window.vaultIconElement(name) : el('div', 'file-icon'));
    const info = el('div', 'file-info');
    const nm = el('div', 'file-name', name);
    if (f.expired) nm.appendChild(el('span', 'expired-tag', L.expired));
    info.append(nm, el('div', 'file-meta',
      (ext ? ext.toUpperCase() : 'FILE') + ' · ' + fmtSize(meta.plaintext_size || 0) + ' · ' +
      L.deleted_on + ' ' + f.deleted_at + ' · ' + L.expires + ' ' + f.expiry));
    content.appendChild(info);

    const group = el('div', 'btn-group');
    const bRestore = el('button', 'btn btn-restore', L.restore); bRestore.type = 'button';
    const bDelete = el('button', 'btn btn-delete', L.delete_permanently); bDelete.type = 'button';
    bRestore.addEventListener('click', () => ask('restore', async () => {
      await api('/api/files/' + f.id + '/restore', { method: 'POST' });
      load();
    }));
    bDelete.addEventListener('click', () => ask('delete', async () => {
      await api('/api/files/' + f.id, { method: 'DELETE' });
      load();
    }));
    group.append(bRestore, bDelete);
    row.append(content, group);
    return row;
  }

  async function load() {
    const empty = document.getElementById('trashEmpty');
    const emptyBtn = document.getElementById('emptyTrashBtn');
    privateKey = await VaultKeyStore.load();
    if (!privateKey) {
      list.innerHTML = '';
      list.appendChild(el('div', 'empty', L.key_expired));
      if (empty) empty.style.display = 'none';
      return;
    }
    const r = await api('/api/trash');
    if (!r.ok) return;
    const rows = [];
    for (const f of r.data.files) rows.push(buildRow(f, await decryptMeta(f)));
    list.innerHTML = '';
    rows.forEach(x => list.appendChild(x));
    const has = r.data.files.length > 0;
    if (empty) empty.style.display = has ? 'none' : '';
    if (emptyBtn) emptyBtn.style.display = has ? '' : 'none';
  }

  const emptyBtn = document.getElementById('emptyTrashBtn');
  if (emptyBtn) {
    emptyBtn.addEventListener('click', () => ask('empty', async () => {
      await api('/api/trash/empty', { method: 'POST' });
      load();
    }));
  }

  window.VaultTrash = { reload: load };
  load();
})();
