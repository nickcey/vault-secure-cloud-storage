/**
 * vault-share.js — Page destinataire d'un lien de partage.
 * La clé de fichier arrive dans le FRAGMENT de l'URL (après #) : le navigateur
 * ne l'envoie jamais au serveur. Nom, taille et contenu sont déchiffrés ici.
 */
(function () {
  'use strict';

  const b64urlToBuf = (b64) => {
    const padded = b64.replace(/-/g, '+').replace(/_/g, '/');
    const bin = atob(padded + '==='.slice((padded.length + 3) % 4));
    const buf = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    return buf;
  };
  function fmtSize(bytes) {
    if (bytes < 1024) return bytes + ' o';
    const units = ['Ko', 'Mo', 'Go', 'To'];
    let v = bytes, i = -1;
    do { v /= 1024; i++; } while (v >= 1024 && i < units.length - 1);
    return v.toFixed(i === 0 ? 0 : 1) + ' ' + units[i];
  }

  const fragment = window.location.hash.slice(1);
  const token = window.location.pathname.split('/').pop();
  const dlBtn = document.getElementById('dlBtn');
  const ready = document.getElementById('shareReady');
  const errorCard = document.getElementById('shareErrorCard');
  const errorMsg = document.getElementById('shareError');
  const setText = (id, v) => { const e = document.getElementById(id); if (e) e.textContent = v; };

  function fail(text) {
    if (ready) ready.style.display = 'none';
    if (errorCard) errorCard.style.display = '';
    if (errorMsg) errorMsg.textContent = text;
  }

  let info = null, meta = null, fileKeyBytes = null;

  async function init() {
    if (!fragment) return fail('Clé de partage manquante : le lien est incomplet.');
    let r;
    try {
      r = await fetch('/api/share/' + encodeURIComponent(token) + '/info', { credentials: 'same-origin' });
    } catch (e) { return fail('Erreur réseau.'); }
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return fail(data.error || 'Lien indisponible.');
    info = data;
    try {
      fileKeyBytes = b64urlToBuf(fragment);
      const metaKey = await vaultImportAesKey(await vaultDeriveMetaKey(fileKeyBytes));
      const raw = b64ToBuf(info.encrypted_meta_b64);
      const pt = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: raw.slice(0, 12) }, metaKey, raw.slice(12));
      meta = JSON.parse(bufToStr(new Uint8Array(pt)));
    } catch (e) {
      return fail('Clé de partage incorrecte : le lien a peut-être été mal copié.');
    }
    setText('shareFileName', meta.filename || 'Fichier');
    setText('shareInfo', fmtSize(meta.plaintext_size || 0));
    setText('shareExpiry', info.expires_at || '');
    if (info.max_downloads > 0) {
      const c = document.getElementById('shareCounter');
      if (c) c.style.display = '';
      setText('shareCount', info.download_count + ' / ' + info.max_downloads);
    }
    if (ready) ready.style.display = '';
    if (dlBtn) dlBtn.disabled = false;
  }

  if (dlBtn) {
    dlBtn.addEventListener('click', async function () {
      if (!info || !meta) return;
      dlBtn.disabled = true;
      dlBtn.textContent = 'Téléchargement en cours...';
      try {
        const fileKey = await vaultImportAesKey(fileKeyBytes);
        const resp = await fetch('/api/share/' + encodeURIComponent(token) + '/blob', { credentials: 'same-origin' });
        if (!resp.ok) {
          const e = await resp.json().catch(() => ({}));
          return fail(e.error || 'Erreur au téléchargement.');
        }
        const raw = new Uint8Array(await resp.arrayBuffer());
        let padded;
        try {
          padded = new Uint8Array(await crypto.subtle.decrypt(
            { name: 'AES-GCM', iv: raw.slice(0, 12) }, fileKey, raw.slice(12)));
        } catch (e) {
          return fail('Clé de partage incorrecte ou fichier modifié.');
        }
        const content = vaultStripPadding(padded, meta.plaintext_size);
        const expected = meta.content_sha256 || info.content_sha256;
        if (expected && (await vaultSha256Hex(content)) !== expected) {
          return fail("L'intégrité du fichier a été compromise.");
        }
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([content], { type: meta.mime_type || 'application/octet-stream' }));
        a.download = meta.filename || 'fichier';
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 10000);
        dlBtn.textContent = '✅ Téléchargé';
        setTimeout(() => { dlBtn.textContent = '⬇ Télécharger le fichier'; dlBtn.disabled = false; }, 4000);
      } catch (err) {
        dlBtn.disabled = false;
        dlBtn.textContent = '⬇ Télécharger le fichier';
        fail('Erreur : ' + err.message);
      }
    });
  }

  init();
})();
