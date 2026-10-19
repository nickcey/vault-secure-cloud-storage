/**
 * vault-trusted.js — Contacts de récupération (Shamir 2 sur 3).
 *
 * Configuration : une clé de récupération aléatoire S (32 octets) est découpée en
 * 3 parts DANS LE NAVIGATEUR (seuil 2). Chaque part est chiffrée avec la clé publique
 * d'un contact. Les contacts reçoivent une invitation et doivent l'accepter ; lors
 * d'une récupération, 2 contacts sur 3 doivent valider.
 */
(function () {
  'use strict';
  const api = (u, o) => VaultPRE.api(u, o);
  const $ = id => document.getElementById(id);
  function msg(id, text, type) {
    const e = $(id); if (!e) return;
    e.textContent = text; e.className = 'flash ' + (type || 'info'); e.style.display = 'block';
  }
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  const BADGE = { pending: ['⏳', 'en attente de réponse', 'b-pending'],
                  accepted: ['✅', 'a accepté', 'b-ok'],
                  declined: ['❌', 'a refusé', 'b-no'] };

  // ── Mes contacts : état ──
  async function loadStatus() {
    const r = await api('/api/recovery-contacts');
    if (!r.ok) return;
    const box = $('contactsStatus');
    box.innerHTML = '';
    if (r.data.configured) {
      box.append(el('p', r.data.ready ? 'status-ok' : 'status-wait', r.data.ready
        ? '✅ Récupération par contacts active : ' + r.data.threshold + ' contacts sur ' + r.data.total + ' devront valider.'
        : '⏳ En attente : au moins ' + r.data.threshold + ' contacts doivent accepter votre invitation pour activer la récupération.'));
      const ul = el('ul', 'contact-list');
      r.data.contacts.forEach(c => {
        const b = BADGE[c.status] || BADGE.pending;
        const li = el('li');
        li.append(document.createTextNode('🛡️ ' + c.username + ' — ' + c.email + ' '), el('span', 'badge ' + b[2], b[0] + ' ' + b[1]));
        ul.appendChild(li);
      });
      box.appendChild(ul);
      if (r.data.contacts.some(c => c.status === 'declined')) {
        box.appendChild(el('p', 'status-off', 'Un contact a refusé : enregistrez une nouvelle liste ci-dessous pour le remplacer.'));
      }
      $('removeContactsBtn').style.display = '';
      $('setupTitle').textContent = 'Changer mes contacts de récupération';
    } else {
      box.append(el('p', 'status-off', 'Aucun contact de récupération. Sans eux, seule votre phrase de 12 mots permet de récupérer votre compte.'));
      $('removeContactsBtn').style.display = 'none';
    }
  }

  // ── Configuration ──
  const form = $('contactsForm');
  if (form) {
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;
      try {
        const email = (document.body.dataset.email || '').toLowerCase();
        const password = $('cfPassword').value;
        const emails = [1, 2, 3].map(n => $('cfContact' + n).value.trim().toLowerCase());
        if (!password || emails.some(x => !x)) throw new Error('Remplissez tous les champs.');
        if (new Set(emails).size !== emails.length) throw new Error('Choisissez trois contacts différents.');
        msg('contactsMsg', 'Vérification du mot de passe...', 'info');

        // 1. La clé privée en clair n'est obtenue qu'ici, avec le mot de passe
        const salt = await api('/get-salt', { json: { email } });
        const { accountKey } = await vaultDeriveKeys(password, hexToBuf(salt.data.salt));
        const m = await VaultPRE.me(true);
        let pkcs8;
        try {
          pkcs8 = await vaultAesDecryptBytes(await vaultImportAesKey(accountKey), JSON.parse(m.encrypted_private_key));
        } catch (err) { throw new Error('Mot de passe incorrect.'); }

        // 2. Clés publiques des trois contacts
        const contacts = [];
        for (const x of emails) {
          contacts.push(await VaultPRE.lookup(x, { requireUmbral: false })
            .catch(err => { throw new Error(x + ' : ' + err.message); }));
        }

        // 3. Secret de récupération découpé en 3 parts (seuil 2) + copie chiffrée de la clé privée
        msg('contactsMsg', 'Découpage de la clé de récupération...', 'info');
        const S = crypto.getRandomValues(new Uint8Array(32));
        const shares = VaultShamir.split(S, 3, 2);
        const { key, auth } = await VaultShamir.deriveFromSecret(S);
        S.fill(0);
        const wrapped = JSON.stringify(await vaultAesEncryptBytes(await vaultImportAesKey(key), pkcs8));
        pkcs8.fill(0);

        // 4. Chaque part chiffrée pour son contact (le serveur ne peut en lire aucune)
        const payload = [];
        for (let n = 0; n < 3; n++) {
          payload.push({ contact_id: contacts[n].id, share_index: n + 1,
                         encrypted_share: await vaultRsaEncrypt(contacts[n].public_key, shares[n + 1]) });
          shares[n + 1].fill(0);
        }
        const r = await api('/api/recovery-contacts', { json: {
          contacts: payload, shamir_wrapped_key: wrapped, shamir_auth_value: bufToHex(auth),
        } });
        if (!r.ok) throw new Error(r.data.error || 'Erreur');
        form.reset();
        msg('contactsMsg', 'Invitations envoyées. Vos contacts doivent les accepter dans leur compte Vault.', 'success');
        loadStatus();
      } catch (err) {
        msg('contactsMsg', err.message, 'error');
      }
      btn.disabled = false;
    });

    $('removeContactsBtn').addEventListener('click', async () => {
      if (!window.confirm('Retirer vos contacts de récupération ? Leurs parts seront supprimées du serveur.')) return;
      await api('/api/recovery-contacts/remove', { json: {} });
      loadStatus();
    });
    loadStatus();
  }

  // ── Invitations reçues (on me propose d'être contact de récupération) ──
  const invHost = $('invitationsList');
  async function loadInvitations() {
    const r = await api('/api/recovery-invitations');
    if (!r.ok) return;
    invHost.innerHTML = '';
    $('invitationsEmpty').style.display = r.data.invitations.length ? 'none' : '';
    for (const inv of r.data.invitations) {
      const row = el('div', 'request-row');
      const info = el('div', 'request-info');
      info.append(el('div', 'request-name', inv.owner + ' (' + inv.owner_email + ')'),
                  el('div', 'request-meta', 'Vous propose d’être son contact de récupération · ' + inv.created_at));
      const btns = el('div', 'row-actions');
      const yes = el('button', 'submit-btn small', 'Accepter'); yes.type = 'button';
      const no = el('button', 'ghost small', 'Refuser'); no.type = 'button';
      const answer = async accept => {
        yes.disabled = no.disabled = true;
        const a = await api('/api/recovery-invitations/' + inv.id + '/respond', { json: { accept } });
        if (a.ok) msg('invitationsMsg', accept ? 'Vous êtes maintenant contact de récupération de ' + inv.owner + '.'
                                               : 'Invitation de ' + inv.owner + ' refusée.', accept ? 'success' : 'info');
        else msg('invitationsMsg', a.data.error || 'Erreur', 'error');
        loadInvitations();
      };
      yes.addEventListener('click', () => answer(true));
      no.addEventListener('click', () => answer(false));
      btns.append(yes, no);
      row.append(info, btns);
      invHost.appendChild(row);
    }
    const acc = $('acceptedList');
    if (acc) {
      acc.innerHTML = '';
      r.data.accepted.forEach(a => acc.appendChild(el('li', '', '🛡️ ' + a.owner + ' — ' + a.owner_email)));
      $('acceptedBox').style.display = r.data.accepted.length ? '' : 'none';
    }
  }
  if (invHost) loadInvitations();

  // ── Demandes de récupération reçues (validation) ──
  const reqHost = $('requestsList');
  async function loadRequests() {
    const r = await api('/api/recovery-requests');
    if (!r.ok) return;
    reqHost.innerHTML = '';
    $('requestsEmpty').style.display = r.data.requests.length ? 'none' : '';
    for (const q of r.data.requests) {
      const row = el('div', 'request-row');
      const info = el('div', 'request-info');
      // Empreinte de la clé pour laquelle MA part va être rechiffrée : le demandeur voit
      // celle de la clé que SON navigateur a créée. Identiques = aucune substitution.
      const fp = await vaultKeyFingerprint(q.temp_public_key);
      const fpLine = el('div', 'request-meta');
      fpLine.append(document.createTextNode('Empreinte de la demande : '), el('span', 'fp', fp));
      info.append(el('div', 'request-name', q.owner + ' (' + q.owner_email + ')'),
                  el('div', 'request-meta', 'Demande de récupération envoyée le ' + q.created_at), fpLine);
      const btn = el('button', 'submit-btn small', 'Valider'); btn.type = 'button';
      btn.addEventListener('click', async () => {
        if (!window.confirm('Avant de valider, appelez ' + q.owner + ' (ou voyez-le en personne) et lisez-lui cette empreinte :\n\n' +
                            fp + '\n\nElle doit être exactement celle qui s’affiche sur son écran. Si elle est différente, ne validez pas.\n\nL’empreinte est-elle identique ?')) return;
        btn.disabled = true;
        try {
          const pk = await VaultKeyStore.load();
          if (!pk) throw new Error('Clé privée expirée — reconnectez-vous.');
          const share = await vaultRsaDecrypt(pk, q.encrypted_share);          // ma part, en clair ici seulement
          const forRequester = await vaultRsaEncrypt(q.temp_public_key, share); // rechiffrée pour le demandeur
          share.fill(0);
          const a = await api('/api/recovery-requests/' + q.request_id + '/approve', { json: { encrypted_share: forRequester } });
          if (!a.ok) throw new Error(a.data.error || 'Erreur');
          msg('requestsMsg', 'Récupération de ' + q.owner + ' validée.', 'success');
          loadRequests();
        } catch (err) { msg('requestsMsg', err.message, 'error'); btn.disabled = false; }
      });
      row.append(info, btn);
      reqHost.appendChild(row);
    }
  }
  if (reqHost) loadRequests();
})();
