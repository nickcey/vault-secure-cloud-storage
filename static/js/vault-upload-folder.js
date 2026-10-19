/** Page d'envoi : affiche le dossier de destination (nom déchiffré dans le navigateur). */
(function () {
  'use strict';
  const id = new URLSearchParams(window.location.search).get('folder');
  if (!id) return;
  const back = document.getElementById('backToDashboard');
  if (back) back.setAttribute('href', '/dashboard?folder=' + encodeURIComponent(id));
  const box = document.getElementById('uploadDestination');
  VaultKeyStore.load().then(pk => (pk ? VaultFolders.open(pk) : null)).then(folders => {
    if (!folders || !box || !folders.exists(id)) return;
    const path = folders.path(id).map(f => f.name).join(' › ');
    const shared = folders.recipientsFor(id);
    box.textContent = 'Destination : 📁 ' + path +
      (shared.length ? ' (partagé avec ' + shared.map(r => r.username).join(', ') + ')' : '');
    box.style.display = 'block';
  }).catch(() => {});
})();
