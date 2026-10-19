/**
 * vault-folders.js — Dossiers chiffrés.
 *
 * L'arborescence n'existe que dans le navigateur. Elle est conservée dans un index
 * propre à chaque utilisateur, chiffré en AES-256-GCM avec une clé aléatoire ; cette
 * clé est elle-même chiffrée avec la clé publique RSA du compte. Le serveur ne stocke
 * qu'un bloc opaque : il ne connaît ni les noms des dossiers, ni leur hiérarchie, ni
 * le dossier de chaque fichier, et continue de voir une simple liste plate de blocs.
 *
 * Contenu de l'index (en clair, uniquement en mémoire) :
 *   { v: 1,
 *     folders: { <id>: { name, parent, created } },     // parent = null pour la racine
 *     files:   { <uuid du fichier>: <id du dossier> },  // absent = racine
 *     shares:  { <id du dossier>: [ { id, email, username } ] } }
 */
const VaultFolders = (function () {
  'use strict';

  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  async function api(url, opts = {}) {
    opts.credentials = 'same-origin';
    opts.headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers, {
      'X-CSRFToken': csrfMeta ? csrfMeta.getAttribute('content') : '',
    });
    const r = await fetch(url, opts);
    return { ok: r.ok, status: r.status, data: await r.json().catch(() => ({})) };
  }

  const PAD = 4096;   // la taille de l'index est arrondie au multiple de 4 Kio supérieur
  const empty = () => ({ v: 1, folders: {}, files: {}, shares: {} });
  const newId = () => bufToHex(crypto.getRandomValues(new Uint8Array(12)));

  async function encryptIndex(keyBytes, index) {
    let json = JSON.stringify(index);
    json += ' '.repeat((PAD - (json.length % PAD)) % PAD);   // espaces : JSON reste valide
    return JSON.stringify(await vaultAesEncryptBytes(await vaultImportAesKey(keyBytes), strToBuf(json)));
  }
  async function decryptIndex(keyBytes, blob) {
    const pt = await vaultAesDecryptBytes(await vaultImportAesKey(keyBytes), JSON.parse(blob));
    const idx = JSON.parse(bufToStr(pt));
    return Object.assign(empty(), idx);
  }

  /** Ouvre l'index de l'utilisateur connecté. privateKey : CryptoKey RSA non exportable. */
  async function open(privateKey) {
    let state = { keyBytes: null, wrappedKey: null, version: 0, index: empty() };

    async function fetchState() {
      const r = await api('/api/folder-index');
      if (!r.ok) throw new Error(r.data.error || 'Index des dossiers indisponible');
      const s = { keyBytes: null, wrappedKey: r.data.key, version: r.data.version || 0, index: empty() };
      if (r.data.key) {
        s.keyBytes = await vaultRsaDecrypt(privateKey, r.data.key);
        if (r.data.index) s.index = await decryptIndex(s.keyBytes, r.data.index);
      }
      return s;
    }
    state = await fetchState();

    /** Applique une modification et l'enregistre ; en cas d'écriture concurrente, relit et rejoue. */
    async function mutate(change) {
      for (let attempt = 0; attempt < 4; attempt++) {
        const draft = JSON.parse(JSON.stringify(state.index));
        const result = change(draft);
        let key = null;
        if (!state.keyBytes) state.keyBytes = crypto.getRandomValues(new Uint8Array(32));
        if (!state.wrappedKey) {   // première utilisation : la clé de l'index part enveloppée
          const me = await api('/api/me');
          key = await vaultRsaEncrypt(me.data.public_key, state.keyBytes);
        }
        const r = await api('/api/folder-index', { method: 'POST', body: JSON.stringify({
          index: await encryptIndex(state.keyBytes, draft), key, version: state.version }) });
        if (r.ok) {
          state.index = draft; state.version = r.data.version;
          if (key) state.wrappedKey = key;
          return result;
        }
        if (r.status !== 409) throw new Error(r.data.error || 'Enregistrement impossible');
        state = await fetchState();   // modifié depuis un autre onglet : on recommence
      }
      throw new Error('Index des dossiers modifié en parallèle, réessayez.');
    }

    const F = () => state.index.folders;
    const exists = id => !!(id && F()[id]);

    function children(parent) {
      return Object.entries(F()).filter(([, f]) => (f.parent || null) === (parent || null))
        .map(([id, f]) => Object.assign({ id }, f))
        .sort((a, b) => a.name.localeCompare(b.name, 'fr', { sensitivity: 'base' }));
    }
    function folderOf(uuid) {
      const id = state.index.files[uuid];
      return exists(id) ? id : null;   // dossier supprimé entre-temps : racine
    }
    function path(id) {
      const out = [];
      const seen = new Set();
      while (exists(id) && !seen.has(id)) { seen.add(id); out.unshift(Object.assign({ id }, F()[id])); id = F()[id].parent; }
      return out;
    }
    function subtree(id) {
      const ids = [id];
      for (let i = 0; i < ids.length; i++) children(ids[i]).forEach(c => ids.push(c.id));
      return ids;
    }
    /** Tous les dossiers, à plat avec indentation (pour la fenêtre « Déplacer »). */
    function flat(parent = null, depth = 0, out = []) {
      children(parent).forEach(c => { out.push({ id: c.id, depth, name: c.name }); flat(c.id, depth + 1, out); });
      return out;
    }
    /** Destinataires d'un dossier et de ses parents : un fichier rangé ici leur est partagé. */
    function recipientsFor(id) {
      const seen = new Map();
      path(id).forEach(f => (state.index.shares[f.id] || []).forEach(r => seen.set(r.id, r)));
      return [...seen.values()];
    }
    function clean(name) {
      name = String(name || '').trim().replace(/[\u0000-\u001f]/g, '');
      if (!name) throw new Error('Nom de dossier vide');
      if (name.length > 120) throw new Error('Nom trop long (120 caractères au plus)');
      return name;
    }

    return {
      get version() { return state.version; },
      exists, children, folderOf, path, subtree, flat, recipientsFor,
      sharesOf: id => (state.index.shares[id] || []).slice(),
      /** Chemin vu par un destinataire : depuis le plus haut dossier partagé avec lui. */
      labelFor(id, recipientId) {
        const p = path(id);
        const i = p.findIndex(f => (state.index.shares[f.id] || []).some(r => r.id === recipientId));
        return i < 0 ? null : p.slice(i).map(f => f.name);
      },
      async reload() { state = await fetchState(); },
      create: (name, parent) => mutate(ix => {
        const id = newId();
        ix.folders[id] = { name: clean(name), parent: exists(parent) ? parent : null, created: new Date().toISOString() };
        return id;
      }),
      rename: (id, name) => mutate(ix => { if (ix.folders[id]) ix.folders[id].name = clean(name); }),
      /** Range des fichiers (uuid) dans un dossier (null = racine). */
      place: (uuids, folderId) => mutate(ix => {
        uuids.forEach(u => { if (folderId && ix.folders[folderId]) ix.files[u] = folderId; else delete ix.files[u]; });
      }),
      /** Déplace un dossier ; refuse de le placer dans lui-même ou un de ses sous-dossiers. */
      moveFolder: (id, parent) => mutate(ix => {
        if (parent && subtree(id).includes(parent)) throw new Error('Impossible de déplacer un dossier dans lui-même');
        if (ix.folders[id]) ix.folders[id].parent = parent && ix.folders[parent] ? parent : null;
      }),
      /** Supprime un dossier et ses sous-dossiers ; renvoie les uuid des fichiers qu'ils contenaient. */
      remove: id => mutate(ix => {
        const ids = new Set(subtree(id));
        const uuids = Object.keys(ix.files).filter(u => ids.has(ix.files[u]));
        ids.forEach(f => { delete ix.folders[f]; delete ix.shares[f]; });
        uuids.forEach(u => delete ix.files[u]);
        return uuids;
      }),
      addShare: (id, recipient) => mutate(ix => {
        const list = ix.shares[id] || (ix.shares[id] = []);
        if (!list.some(r => r.id === recipient.id)) list.push({ id: recipient.id, email: recipient.email, username: recipient.username, delegated: !!recipient.has_delegation });
      }),
      dropShare: (id, recipientId) => mutate(ix => {
        if (ix.shares[id]) ix.shares[id] = ix.shares[id].filter(r => r.id !== recipientId);
        if (ix.shares[id] && !ix.shares[id].length) delete ix.shares[id];
      }),
      /** Note qu'une délégation existe pour ce destinataire (une révocation sera alors détectable). */
      markDelegated: recipientId => mutate(ix => {
        Object.values(ix.shares).forEach(list => list.forEach(r => { if (r.id === recipientId) r.delegated = true; }));
      }),
      /** Retire un destinataire de tous les dossiers (après révocation du partage). */
      forgetRecipient: recipientId => mutate(ix => {
        Object.keys(ix.shares).forEach(f => {
          ix.shares[f] = ix.shares[f].filter(r => r.id !== recipientId);
          if (!ix.shares[f].length) delete ix.shares[f];
        });
      }),
    };
  }

  return { open };
})();
