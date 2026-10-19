/**
 * vault-files.js — Upload / liste / téléchargement / partage / corbeille.
 * Tout le chiffrement se fait dans le navigateur (Web Crypto uniquement).
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
    return { ok: r.ok, status: r.status, data: await r.json().catch(() => ({})) };
  }

  function fmtSize(bytes) {
    if (bytes < 1024) return bytes + ' o';
    const units = ['Ko', 'Mo', 'Go', 'To'];
    let v = bytes, i = -1;
    do { v /= 1024; i++; } while (v >= 1024 && i < units.length - 1);
    return v.toFixed(i === 0 ? 0 : 1) + ' ' + units[i];
  }

  // ═══════════════ DOSSIERS PARTAGÉS ═══════════════
  /**
   * Partage des fichiers avec les destinataires d'un dossier (et de ses parents).
   * items : [{ f: enregistrement de /api/files, key: octets de la clé du fichier }].
   * Un destinataire dont le partage a été révoqué est retiré du dossier, sans être
   * re-partagé à son insu.
   */
  async function shareIntoFolder(folders, folderId, items) {
    if (!folderId || !items.length || !window.VaultPRE) return 0;
    let n = 0;
    for (const rec of folders.recipientsFor(folderId)) {
      let who;
      try { who = await VaultPRE.lookup(rec.email); } catch (e) { continue; }
      if (who.id !== rec.id) continue;                     // adresse réattribuée : on ne partage pas
      if (!who.has_delegation && rec.delegated) { await folders.forgetRecipient(rec.id); continue; }
      const folderPath = folders.labelFor ? folders.labelFor(folderId, rec.id) : null;
      for (const it of items) {
        await VaultPRE.shareWithUser(it.f, it.key, who, folderPath ? { folderPath } : undefined);
        it.f.has_capsule = true;
        who.has_delegation = true;
        n++;
      }
      if (!rec.delegated) await folders.markDelegated(rec.id);
    }
    return n;
  }
  window.VaultFolderShare = { shareIntoFolder };

  // ═══════════════ UPLOAD (client chiffre tout) ═══════════════

  function xhrUpload(fd, onPct) {
    return new Promise((resolve) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', '/upload');
      xhr.withCredentials = true;
      xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
      if (csrfMeta) xhr.setRequestHeader('X-CSRFToken', csrfMeta.getAttribute('content'));
      xhr.timeout = 600000;
      xhr.upload.addEventListener('progress', e => {
        if (e.lengthComputable && onPct) onPct(Math.round((e.loaded / e.total) * 100));
      });
      const done = (ok, data) => resolve({ ok, data: data || {} });
      xhr.addEventListener('load', () => {
        let data = {};
        try { data = JSON.parse(xhr.responseText); } catch (e) { /* réponse non JSON */ }
        done(xhr.status >= 200 && xhr.status < 300, data);
      });
      xhr.addEventListener('error', () => done(false, { error: 'Erreur réseau pendant l\'envoi.' }));
      xhr.addEventListener('timeout', () => done(false, { error: 'Envoi trop long.' }));
      xhr.send(fd);
    });
  }

  /**
   * Chiffre puis envoie des fichiers. report(texte, pourcentage global 0-100).
   * Renvoie { uploaded, errors: [message] }.
   */
  async function uploadFiles(files, report) {
    report = report || function () {};
    const errors = [];
    let uploaded = 0;
    const privateKey = await VaultKeyStore.load();
    if (!privateKey) return { uploaded, errors: ['Clé privée expirée. Reconnectez-vous.'] };
    // Clé publique du propriétaire (publique : aucun secret)
    const pubResp = await api('/api/me');
    if (!pubResp.ok) return { uploaded, errors: ['Session expirée.'] };
    const pubkeyB64 = pubResp.data.public_key;

    const done = [];   // fichiers déposés : { f, key } pour le rangement dans un dossier
    const n = files.length;
    for (let idx = 0; idx < n; idx++) {
      const f = files[idx];
      const base = (idx / n) * 100;
      report('Chiffrement de ' + f.name + '...', Math.round(base));
      try {
        // 1. Clé de fichier AES-256 aléatoire
        const fileKeyBytes = crypto.getRandomValues(new Uint8Array(32));
        const fileKey = await vaultImportAesKey(fileKeyBytes);

        // 2. Remplissage pour masquer la taille exacte
        const plainBuf = new Uint8Array(await f.arrayBuffer());
        const paddedSize = vaultGetPaddedSize(plainBuf.length + 16);
        const content_sha256 = await vaultSha256Hex(plainBuf);
        let padded = vaultAddPadding(plainBuf, paddedSize - 16);

        // 3. AES-256-GCM du contenu, directement en binaire (gros fichiers :
        //    pas de conversion base64 qui multiplierait la mémoire utilisée)
        report('Chiffrement de ' + f.name + '...', Math.round(base));
        const ivBytes = crypto.getRandomValues(new Uint8Array(12));
        const ctBuf = await crypto.subtle.encrypt({ name: 'AES-GCM', iv: ivBytes }, fileKey, padded);
        padded = null;   // libère la copie en clair remplie
        const payloadBytes = new Uint8Array(12 + ctBuf.byteLength);
        payloadBytes.set(ivBytes, 0);
        payloadBytes.set(new Uint8Array(ctBuf), 12);
        const enc = { iv: bufToHex(ivBytes) };

        // 4. Clé de fichier enveloppée avec la clé publique RSA du compte
        const envelopeKeyB64 = await vaultRsaEncrypt(pubkeyB64, fileKeyBytes);

        // 5. Métadonnées (nom, type, taille, date) chiffrées avec une clé dérivée (HKDF)
        const metaKey = await vaultImportAesKey(await vaultDeriveMetaKey(fileKeyBytes));
        const metaEnc = await vaultAesEncryptBytes(metaKey, strToBuf(JSON.stringify({
          filename: f.name,
          mime_type: f.type || 'application/octet-stream',
          plaintext_size: plainBuf.length,
          padded_size: paddedSize,
          content_sha256,            // empreinte du contenu : chiffrée, jamais visible du serveur
          uploaded_at: new Date().toISOString(),
        })));
        const metaB64 = bufToB64(new Uint8Array([...hexToBuf(metaEnc.iv), ...b64ToBuf(metaEnc.ct)]));

        // 6. Empreintes pour détecter toute modification côté serveur
        const blob_sha256 = await vaultSha256Hex(payloadBytes);

        // 7. Envoi du blob chiffré
        const fd = new FormData();
        fd.append('file', new Blob([payloadBytes]), 'payload.enc');
        fd.append('uuid', crypto.randomUUID ? crypto.randomUUID() : vaultRandomHex(16));
        fd.append('aes_iv', enc.iv);
        fd.append('encrypted_file_key', envelopeKeyB64);
        fd.append('encrypted_metadata', metaB64);
        fd.append('metadata_sha256', blob_sha256);
        fd.append('padded_size', payloadBytes.length);
        if (csrfMeta) fd.append('csrf_token', csrfMeta.getAttribute('content'));

        const resp = await xhrUpload(fd, pct => {
          report('Envoi de ' + f.name + '... ' + pct + '%', Math.round(base + pct / n));
        });
        if (!resp.ok) { errors.push(f.name + ' : ' + (resp.data.error || 'échec')); continue; }
        uploaded++;
        done.push({ f: { id: resp.data.file_id, uuid: resp.data.uuid, has_capsule: false }, key: fileKeyBytes });
      } catch (err) {
        errors.push(f.name + ' : erreur de chiffrement (' + err.message + ')');
      }
    }
    // Rangement dans le dossier courant (index chiffré) et partage avec ses destinataires
    const target = new URLSearchParams(window.location.search).get('folder');
    if (target && done.length && typeof VaultFolders !== 'undefined') {
      try {
        report('Rangement dans le dossier...', 100);
        const folders = await VaultFolders.open(privateKey);
        if (folders.exists(target)) {
          await folders.place(done.map(d => d.f.uuid), target);
          if (folders.recipientsFor(target).length) {
            report('Partage avec les destinataires du dossier...', 100);
            await shareIntoFolder(folders, target, done);
          }
        }
      } catch (err) {
        errors.push('Fichiers déposés, mais rangement dans le dossier impossible (' + err.message + ')');
      }
    }
    report(errors.length ? 'Terminé avec des erreurs.' : 'Terminé !', 100);
    return { uploaded, errors };
  }
  window.VaultUpload = { uploadFiles };

  // ═══════════════ DASHBOARD (liste déchiffrée client) ═══════════════
  // Le rendu reprend le design de la page (lignes, menus, fenêtres) ; la page
  // fournit les fenêtres via window.VaultDashboardUI (renommer, partager, supprimer).

  const dashTable = document.getElementById('filesTableBody');
  if (dashTable) {
    let privateKey = null;
    const fileKeyCache = {};   // clé de fichier (octets) par uuid, en mémoire uniquement
    const L = Object.assign({ rename: 'Renommer', download: 'Télécharger', share: 'Partager',
      delete: 'Supprimer', expired: 'Clé privée expirée — reconnectez-vous.' }, window.VAULT_I18N || {});

    async function getFileKeyBytes(f) {
      if (!fileKeyCache[f.uuid]) {
        if (!privateKey) privateKey = await VaultKeyStore.load();
        fileKeyCache[f.uuid] = await vaultRsaDecrypt(privateKey, f.encrypted_file_key);
      }
      return fileKeyCache[f.uuid];
    }

    async function decryptMeta(f) {
      // Clé méta = HKDF(clé de fichier)
      try {
        const metaKey = await vaultImportAesKey(await vaultDeriveMetaKey(await getFileKeyBytes(f)));
        const raw = b64ToBuf(f.encrypted_metadata);   // iv(12) || ct || tag
        const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: raw.slice(0, 12) }, metaKey, raw.slice(12));
        return JSON.parse(bufToStr(new Uint8Array(pt)));
      } catch (e) {
        return { filename: 'fichier-illisible-' + f.uuid.slice(0, 8), plaintext_size: 0 };
      }
    }

    function el(tag, cls, text) {
      const e = document.createElement(tag);
      if (cls) e.className = cls;
      if (text !== undefined) e.textContent = text;
      return e;
    }

    function menuItem(icon, label, cls) {
      const b = el('button', 'dropdown-item' + (cls ? ' ' + cls : ''));
      b.type = 'button';
      b.append(el('span', '', icon), document.createTextNode(' ' + label));
      return b;
    }

    // ── Dossiers (index chiffré, voir vault-folders.js) ──
    let folders = null;
    let entries = [];   // [{ f, meta }] : tous les fichiers, toutes dossiers confondus
    let current = new URLSearchParams(window.location.search).get('folder') || null;
    const searchBox = document.getElementById('fileSearch');
    const crumbs = document.getElementById('folderBreadcrumb');
    const ui = window.VaultDashboardUI || {};

    function fmtDate(iso) {
      const d = new Date(iso);
      if (isNaN(d)) return '';
      const p2 = x => String(x).padStart(2, '0');
      return p2(d.getUTCDate()) + '/' + p2(d.getUTCMonth() + 1) + '/' + d.getUTCFullYear() + ' ' + p2(d.getUTCHours()) + ':' + p2(d.getUTCMinutes());   // comme les dates du serveur
    }
    function folderEntries(id) {   // fichiers d'un dossier et de ses sous-dossiers
      const ids = new Set(folders.subtree(id));
      return entries.filter(e => ids.has(folders.folderOf(e.f.uuid)));
    }
    function moveOptions(exclude) {
      const skip = new Set(exclude ? folders.subtree(exclude) : []);
      return [{ id: '', label: 'Mes fichiers' }].concat(folders.flat()
        .filter(o => !skip.has(o.id))
        .map(o => ({ id: o.id, label: '    '.repeat(o.depth + 1) + '📁 ' + o.name })));
    }
    function setFolder(id) {
      current = id && folders && folders.exists(id) ? id : null;
      const url = window.location.pathname + (current ? '?folder=' + current : '');
      window.history.replaceState(null, '', url);
      if (searchBox) searchBox.value = '';
      render();
    }
    function updateUploadLinks() {
      const href = '/upload' + (current ? '?folder=' + current : '');
      document.querySelectorAll('a').forEach(a => {
        if ((a.getAttribute('href') || '').split('?')[0] === '/upload') a.setAttribute('href', href);
      });
    }
    function renderCrumbs() {
      if (!crumbs) return;
      crumbs.innerHTML = '';
      crumbs.style.display = current ? '' : 'none';   // à la racine, le titre suffit
      const trail = [{ id: null, name: 'Mes fichiers' }].concat(folders ? folders.path(current) : []);
      trail.forEach((c, i) => {
        if (i) crumbs.appendChild(el('span', 'crumb-sep', '›'));
        if (i === trail.length - 1) crumbs.appendChild(el('span', 'crumb-current', c.name));
        else {
          const a = el('a', '', c.name); a.href = '#';
          a.addEventListener('click', ev => { ev.preventDefault(); setFolder(c.id); });
          crumbs.appendChild(a);
        }
      });
    }

    function buildRow(f, meta, where) {
      const tr = document.createElement('tr');
      const name = meta.filename || 'fichier';
      const ext = (window.vaultFileIcon ? window.vaultFileIcon(name).ext : '') || '';

      const td1 = el('td'), cell = el('div', 'file-name-cell');
      cell.appendChild(window.vaultIconElement ? window.vaultIconElement(name) : el('div', 'file-icon'));
      const txt = el('div');
      txt.append(el('div', 'file-name-text', name), el('div', 'file-meta', (ext ? ext.toUpperCase() : 'FILE') + (where ? ' · ' + where : '')));
      cell.appendChild(txt); td1.appendChild(cell);

      const td2 = el('td', 'file-size', fmtSize(meta.plaintext_size || 0));
      const td3 = el('td', 'file-date', f.uploaded_at);

      const td4 = el('td'), actions = el('div', 'file-actions');
      const menuBtn = el('button', 'menu-btn', '⋮'); menuBtn.type = 'button'; menuBtn.title = 'Options';
      const menu = el('div', 'dropdown-menu');
      const bRename = menuItem('✏️', L.rename), bDl = menuItem('⬇️', L.download),
            bMove = menuItem('📂', 'Déplacer'), bShare = menuItem('🔗', L.share), bDel = menuItem('🗑️', L.delete, 'danger');
      menu.append(bRename, bDl, bMove, bShare, el('div', 'dropdown-divider'), bDel);
      actions.append(menuBtn, menu); td4.appendChild(actions);
      tr.append(td1, td2, td3, td4);

      const close = wireMenu(tr, menuBtn, menu);
      bDl.addEventListener('click', () => { close(); downloadFile(f); });
      bRename.addEventListener('click', () => {
        close();
        if (ui.showRename) ui.showRename(name, newName => renameFile(f, newName));
        else { const n = window.prompt(L.rename, name); if (n) renameFile(f, n); }
      });
      bMove.addEventListener('click', () => {
        close();
        ui.showMove(name, moveOptions(null), folders.folderOf(f.uuid) || '', async target => {
          try {
            target = target || null;
            await folders.place([f.uuid], target);
            await VaultFolderShare.shareIntoFolder(folders, target, [{ f, key: await getFileKeyBytes(f) }]);
            render();
          } catch (e) { alert('Déplacement impossible : ' + e.message); }
        });
      });
      bShare.addEventListener('click', () => {
        close();
        if (ui.showShare) {
          ui.showShare(name, (h, m) => shareFile(f, h, m), {
            // Partage avec un utilisateur Vault (proxy re-encryption)
            lookup: email => VaultPRE.lookup(email),
            shareUser: async recipient => {
              await VaultPRE.shareWithUser(f, await getFileKeyBytes(f), recipient);
              f.has_capsule = true;
            },
          });
        } else shareFile(f, 24, 0).then(u => u && window.prompt(L.share, u));
      });
      bDel.addEventListener('click', () => {
        close();
        const go = async () => { await api('/api/files/' + f.id + '/trash', { method: 'POST' }); loadFiles(); };
        if (ui.confirmDelete) ui.confirmDelete(go); else go();
      });
      return tr;
    }

    function wireMenu(tr, menuBtn, menu) {
      menuBtn.addEventListener('click', ev => {
        ev.stopPropagation();
        document.querySelectorAll('.dropdown-menu.open').forEach(m => { if (m !== menu) m.classList.remove('open'); });
        document.querySelectorAll('tr.menu-open').forEach(r => { if (r !== tr) r.classList.remove('menu-open'); });
        menu.classList.toggle('open');
        tr.classList.toggle('menu-open', menu.classList.contains('open'));
      });
      return () => { menu.classList.remove('open'); tr.classList.remove('menu-open'); };
    }

    /** Après un renommage ou un déplacement : met à jour les chemins vus par les destinataires. */
    async function relabel(folderId) {
      try {
        for (const id of folders.subtree(folderId)) {
          if (!folders.recipientsFor(id).length) continue;
          const items = [];
          for (const e of entries) if (folders.folderOf(e.f.uuid) === id) items.push({ f: e.f, key: await getFileKeyBytes(e.f) });
          await VaultFolderShare.shareIntoFolder(folders, id, items);
        }
      } catch (e) { console.error('Mise à jour des chemins partagés', e); }
    }

    function buildFolderRow(fo, where) {
      const tr = document.createElement('tr');
      tr.className = 'folder-row';
      const inside = folderEntries(fo.id);
      const subs = folders.subtree(fo.id).length - 1;
      const shared = folders.recipientsFor(fo.id);

      const td1 = el('td'), cell = el('div', 'file-name-cell');
      const icon = el('div', 'file-icon', '📁'); icon.style.fontSize = '20px';
      cell.appendChild(icon);
      const txt = el('div');
      const nameEl = el('div', 'file-name-text', fo.name);
      if (shared.length) nameEl.appendChild(el('span', 'folder-shared', '👥 ' + shared.map(r => r.username).join(', ')));
      const count = inside.length + ' fichier' + (inside.length > 1 ? 's' : '') +
        (subs ? ' · ' + subs + ' sous-dossier' + (subs > 1 ? 's' : '') : '');
      txt.append(nameEl, el('div', 'file-meta', 'DOSSIER · ' + count + (where ? ' · ' + where : '')));
      cell.appendChild(txt); td1.appendChild(cell);
      td1.addEventListener('click', () => setFolder(fo.id));

      const total = inside.reduce((t, e) => t + (e.meta.plaintext_size || 0), 0);
      const td2 = el('td', 'file-size', inside.length ? fmtSize(total) : '—');
      const td3 = el('td', 'file-date', fmtDate(fo.created));

      const td4 = el('td'), actions = el('div', 'file-actions');
      const menuBtn = el('button', 'menu-btn', '⋮'); menuBtn.type = 'button'; menuBtn.title = 'Options';
      const menu = el('div', 'dropdown-menu');
      const bOpen = menuItem('📂', 'Ouvrir'), bRename = menuItem('✏️', L.rename),
            bMove = menuItem('↪️', 'Déplacer'), bShare = menuItem('👥', 'Partager le dossier'),
            bDel = menuItem('🗑️', L.delete, 'danger');
      const own = (folders.sharesOf ? folders.sharesOf(fo.id) : []);
      const bUnshare = own.length ? menuItem('🚫', 'Arrêter le partage') : null;
      menu.append(bOpen, bRename, bMove, bShare);
      if (bUnshare) menu.append(bUnshare);
      menu.append(el('div', 'dropdown-divider'), bDel);
      actions.append(menuBtn, menu); td4.appendChild(actions);
      tr.append(td1, td2, td3, td4);

      const close = wireMenu(tr, menuBtn, menu);
      bOpen.addEventListener('click', () => { close(); setFolder(fo.id); });
      bRename.addEventListener('click', () => {
        close();
        ui.showRename(fo.name, async n => {
          try { await folders.rename(fo.id, n); render(); await relabel(fo.id); } catch (e) { alert(e.message); }
        }, { title: 'Renommer le dossier', label: 'Nouveau nom du dossier' });
      });
      bMove.addEventListener('click', () => {
        close();
        ui.showMove(fo.name, moveOptions(fo.id), fo.parent || '', async target => {
          try {
            target = target || null;
            await folders.moveFolder(fo.id, target);
            const items = [];
            for (const e of folderEntries(fo.id)) items.push({ f: e.f, key: await getFileKeyBytes(e.f) });
            await VaultFolderShare.shareIntoFolder(folders, target, items);
            render();
            await relabel(fo.id);
          } catch (e) { alert('Déplacement impossible : ' + e.message); }
        });
      });
      bShare.addEventListener('click', () => {
        close();
        ui.showShare('📁 ' + fo.name, null, {
          lookup: email => VaultPRE.lookup(email),
          shareUser: async recipient => {
            const list = folderEntries(fo.id);
            for (const e of list) {
              // Chemin relatif au dossier partagé, chiffré pour le destinataire
              const sub = folders.path(folders.folderOf(e.f.uuid));
              const at = sub.findIndex(x => x.id === fo.id);
              const folderPath = sub.slice(at < 0 ? sub.length - 1 : at).map(x => x.name);
              await VaultPRE.shareWithUser(e.f, await getFileKeyBytes(e.f), recipient, { folderPath });
              e.f.has_capsule = true;
              recipient.has_delegation = true;
            }
            await folders.addShare(fo.id, recipient);
            render();
            return 'Dossier partagé avec ' + recipient.username + ' : ' + list.length + ' fichier' +
              (list.length > 1 ? 's' : '') + '. Les fichiers que vous y ajouterez lui seront aussi partagés.';
          },
        });
      });
      if (bUnshare) bUnshare.addEventListener('click', () => {
        close();
        const names = own.map(r => r.username).join(', ');
        ui.confirmDelete(async () => {
          try {
            const uuids = new Set(folderEntries(fo.id).map(e => e.f.uuid));
            const emails = new Set(own.map(r => r.email));
            const r = await api('/api/my-user-shares');
            for (const sh of (r.data.shares || [])) {
              if (uuids.has(sh.uuid) && emails.has(sh.recipient.email)) {
                await api('/api/user-shares/' + sh.share_id + '/revoke', { method: 'POST' });
              }
            }
            for (const rec of own) await folders.dropShare(fo.id, rec.id);
            render();
          } catch (e) { alert('Arrêt du partage impossible : ' + e.message); }
        }, { title: 'Arrêter le partage du dossier',
             text: 'Le dossier « ' + fo.name + ' » ne sera plus partagé avec ' + names +
                   '. Le serveur ne pourra plus leur re-chiffrer les fichiers qu\'il contient ; ce qu\'ils ont déjà téléchargé reste chez eux.' });
      });
      bDel.addEventListener('click', () => {
        close();
        const n = folderEntries(fo.id).length;
        const go = async () => {
          try {
            const uuids = new Set(await folders.remove(fo.id));
            for (const e of entries) if (uuids.has(e.f.uuid)) await api('/api/files/' + e.f.id + '/trash', { method: 'POST' });
            if (current && !folders.exists(current)) current = fo.parent && folders.exists(fo.parent) ? fo.parent : null;
            loadFiles();
          } catch (e) { alert('Suppression impossible : ' + e.message); }
        };
        ui.confirmDelete(go, { title: 'Supprimer le dossier',
          text: 'Le dossier « ' + fo.name + ' » et ses sous-dossiers seront supprimés' +
                (n ? ' ; les ' + n + ' fichier' + (n > 1 ? 's' : '') + ' qu\'ils contiennent iront dans la corbeille.' : '.') });
      });
      return tr;
    }

    function render() {
      const table = dashTable.closest('table');
      const empty = document.getElementById('emptyState');
      if (folders && current && !folders.exists(current)) current = null;
      const q = searchBox ? searchBox.value.trim().toLowerCase() : '';
      const where = uuid => {
        const p = folders.path(folders.folderOf(uuid));
        return p.length ? '📁 ' + p.map(x => x.name).join(' › ') : '';
      };
      const rows = [];
      if (q) {
        folders.flat().filter(o => o.name.toLowerCase().includes(q)).forEach(o => {
          const fo = Object.assign({ id: o.id }, folders.path(o.id).slice(-1)[0]);
          const parent = folders.path(fo.parent);
          rows.push(buildFolderRow(fo, parent.length ? '📁 ' + parent.map(x => x.name).join(' › ') : ''));
        });
        entries.filter(e => (e.meta.filename || '').toLowerCase().includes(q))
          .forEach(e => rows.push(buildRow(e.f, e.meta, where(e.f.uuid))));
      } else {
        folders.children(current).forEach(fo => rows.push(buildFolderRow(fo)));
        entries.filter(e => folders.folderOf(e.f.uuid) === current)
          .forEach(e => rows.push(buildRow(e.f, e.meta)));
      }
      dashTable.innerHTML = '';
      rows.forEach(tr => dashTable.appendChild(tr));
      const nothingAtAll = !entries.length && !folders.children(null).length;
      if (!rows.length && !nothingAtAll) {
        const tr = el('tr', 'empty-row'), td = el('td', '', q ? 'Aucun fichier ni dossier ne correspond à « ' + q + ' ».'
          : 'Ce dossier est vide. Téléversez des fichiers ici ou déplacez-y des fichiers existants.');
        td.colSpan = 4;
        tr.appendChild(td); dashTable.appendChild(tr);
      }
      if (table) table.style.display = nothingAtAll && !current ? 'none' : '';
      if (empty) empty.style.display = nothingAtAll && !current ? '' : 'none';
      renderCrumbs();
      updateUploadLinks();
      // « Téléverser ici » n'apparaît que dans un dossier ouvert
      const here = document.getElementById('uploadHereBtn');
      if (here) here.style.display = current ? '' : 'none';
    }

    function setText(id, v) { const e = document.getElementById(id); if (e) e.textContent = v; }

    async function loadFiles() {
      privateKey = await VaultKeyStore.load();
      const table = dashTable.closest('table');
      const empty = document.getElementById('emptyState');
      if (!privateKey) {
        dashTable.innerHTML = '';
        const tr = el('tr'), td = el('td', 'empty-state', L.expired); td.colSpan = 4;
        tr.appendChild(td); dashTable.appendChild(tr);
        if (table) table.style.display = '';
        if (empty) empty.style.display = 'none';
        return;
      }
      const r = await api('/api/files');
      if (!r.ok) return;
      try {
        if (!folders) folders = await VaultFolders.open(privateKey); else await folders.reload();
      } catch (e) {
        folders = null;
        console.error('Index des dossiers illisible', e);
      }
      if (!folders) {   // index illisible : liste plate, sans perdre l'accès aux fichiers
        folders = { exists: () => false, children: () => [], folderOf: () => null, path: () => [], subtree: id => [id],
                    flat: () => [], recipientsFor: () => [] };
      }
      const list = [];
      for (const f of r.data.files) list.push({ f, meta: await decryptMeta(f) });
      entries = list;
      render();
      setText('filesCount', r.data.files.length);
      setText('statUsed', fmtSize(r.data.total_used));
      setText('statQuota', fmtSize(r.data.total_quota));
      document.dispatchEvent(new CustomEvent('vault:files-loaded'));
    }

    if (searchBox) searchBox.addEventListener('input', () => { if (folders) render(); });
    const newBtn = document.getElementById('newFolderBtn');
    if (newBtn) newBtn.addEventListener('click', () => {
      if (!folders || !folders.create) return alert(L.expired);
      ui.showRename('', async n => {
        try { await folders.create(n, current); render(); } catch (e) { alert(e.message); }
      }, { title: 'Nouveau dossier', label: 'Nom du dossier' });
    });

    async function downloadFile(f) {
      privateKey = await VaultKeyStore.load();
      if (!privateKey) { alert(L.expired); return; }
      try {
        const fileKey = await vaultImportAesKey(await getFileKeyBytes(f));

        // 1. Ticket de téléchargement (ne contient aucune clé)
        const tk = await api('/api/download/create/' + f.id, { method: 'POST' });
        if (!tk.ok) return alert('Erreur : ' + (tk.data.error || 'ticket refusé'));

        // 2. Blob chiffré : iv(12) || ciphertext || tag(16)
        progressMsg('Téléchargement du fichier chiffré...');
        const resp = await fetch('/api/download-file/' + tk.data.token, { credentials: 'same-origin' });
        if (!resp.ok) {
          const e = await resp.json().catch(() => ({}));
          return alert('Erreur : ' + (e.error || 'téléchargement refusé'));
        }
        const raw = new Uint8Array(await resp.arrayBuffer());

        // 3. Déchiffrement local : le tag AES-GCM rejette toute modification
        let plaintextPadded;
        try {
          plaintextPadded = new Uint8Array(await crypto.subtle.decrypt(
            { name: 'AES-GCM', iv: raw.slice(0, 12) }, fileKey, raw.slice(12)));
        } catch (e) {
          return alert('Fichier modifié ou corrompu : déchiffrement refusé.');
        }

        // 4. Retrait du remplissage
        const meta = await decryptMeta(f);
        const content = vaultStripPadding(plaintextPadded, meta.plaintext_size);
        const expected = meta.content_sha256 || f.content_sha256;   // anciens fichiers : champ serveur
        if (expected && (await vaultSha256Hex(content)) !== expected) {
          return alert('Intégrité du fichier compromise (contenu modifié).');
        }

        // 5. Enregistrement local
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([content], { type: meta.mime_type || 'application/octet-stream' }));
        a.download = meta.filename || 'fichier';
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 10000);
      } catch (err) {
        alert('Erreur de déchiffrement : ' + err.message);
      }
    }

    async function renameFile(f, newName) {
      newName = String(newName || '').trim();
      if (!newName) return;
      privateKey = await VaultKeyStore.load();
      if (!privateKey) { alert(L.expired); return; }
      const metaJson = await decryptMeta(f);
      metaJson.filename = newName;
      const metaKey = await vaultImportAesKey(await vaultDeriveMetaKey(await getFileKeyBytes(f)));
      const encMeta = await vaultAesEncryptBytes(metaKey, strToBuf(JSON.stringify(metaJson)));
      const ivB = hexToBuf(encMeta.iv), ctB = b64ToBuf(encMeta.ct);
      const both = new Uint8Array(ivB.length + ctB.length);
      both.set(ivB, 0); both.set(ctB, ivB.length);
      const r = await api('/api/files/' + f.id + '/rename', { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ encrypted_metadata: bufToB64(both) }) });
      if (r.ok) loadFiles(); else alert('Erreur : ' + (r.data.error || 'renommage refusé'));
    }

    // Renvoie l'URL complète ; la clé de fichier va UNIQUEMENT dans le fragment (#).
    async function shareFile(f, expiryHours, maxDownloads) {
      const r = await api('/api/share/create/' + f.id, { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expiry_hours: parseInt(expiryHours, 10) || 24,
                               max_downloads: parseInt(maxDownloads, 10) || 0 }) });
      if (!r.ok) { alert('Erreur : ' + (r.data.error || 'partage refusé')); return null; }
      const fileKeyBytes = await getFileKeyBytes(f);
      const fragment = bufToB64(fileKeyBytes).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
      return r.data.url_base + '#' + fragment;
    }

    loadFiles();
    // Clés de partage Umbral : créées automatiquement à la première visite
    if (window.VaultPRE) VaultPRE.ensureKeys().catch(() => {});
  }

  function progressMsg(text) {
    const el = document.getElementById('progressText');
    if (el) el.textContent = text;
  }
})();
