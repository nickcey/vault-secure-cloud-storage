/** Bandeau du tableau de bord : invitations et demandes de récupération reçues. */
(function () {
  'use strict';
  const banner = document.getElementById('recoveryRequestBanner');
  if (!banner) return;
  const get = u => fetch(u, { credentials: 'same-origin' }).then(r => (r.ok ? r.json() : {})).catch(() => ({}));
  Promise.all([get('/api/recovery-requests'), get('/api/recovery-invitations')]).then(([rq, inv]) => {
    const reqs = rq.requests || [], invs = inv.invitations || [];
    let text = '';
    if (reqs.length === 1) text = reqs[0].owner + ' vous demande de valider la récupération de son compte.';
    else if (reqs.length > 1) text = reqs.length + ' demandes de récupération attendent votre validation.';
    else if (invs.length === 1) text = invs[0].owner + ' vous propose d’être son contact de récupération.';
    else if (invs.length > 1) text = invs.length + ' invitations à devenir contact de récupération vous attendent.';
    if (!text) return;
    document.getElementById('recoveryRequestText').textContent = text;
    banner.style.display = 'block';
  });
})();
