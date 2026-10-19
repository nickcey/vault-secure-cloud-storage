/**
 * vault-keystore.js — Stockage de la clé privée dans l'iframe-safe
 * C'est la clé privée déchiffrée (CryptoKey RSA non exportable) qui vit dans
 * IndexedDB, effacée à la déconnexion ET après 10 minutes d'inactivité.
 *
 * Clé d'accès vise à :
 * 1. Ne jamais stocker une clé privée en clair (la CryptoKey RSA
 *    est déjà non exportable par nature) ;
 * 2. Gérer le TTL d'inactivité (délai de la session utilisateur, 10 min) ;
 * 3. Purger IndexedDB à la déconnexion.
 */

const VAULT_INACTIVITY_MS = 10 * 60 * 1000;  // 10 minutes

const VaultKeyStore = (function () {
  'use strict';

  const DB_NAME = 'vault-keystore';
  const STORE = 'keys';
  const ENTRY_ID = 'private-key';
  let _db = null;

  function openDB() {
    return new Promise((resolve, reject) => {
      if (_db) return resolve(_db);
      const req = indexedDB.open(DB_NAME, 1);
      req.onupgradeneeded = (e) => {
        const db = e.target.result;
        if (!db.objectStoreNames.contains(STORE)) {
          db.createObjectStore(STORE);
        }
      };
      req.onsuccess = () => { _db = req.result; resolve(_db); };
      req.onerror = () => reject(req.error);
    });
  }

  /**
   * Stocke la clé privée CryptoKey (non exportable) + le dernier accès.
   * On ne stocke QUE la CryptoKey, jamais une sémantique octets.
   * @param {CryptoKey} privateKey
   */
  async function save(privateKey) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.objectStore(STORE).put(
        { key: privateKey, saved_at: Date.now() }, ENTRY_ID);
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
    });
  }

  /** Lit la clé privée CryptoKey. Inexistante ou TTL dépassé → null. */
  async function load() {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readonly');
      const req = tx.objectStore(STORE).get(ENTRY_ID);
      req.onsuccess = () => {
        const rec = req.result;
        if (!rec) return resolve(null);
        if (Date.now() - rec.saved_at > VAULT_INACTIVITY_MS) {
          clear();  // exégration après inactivité
          return resolve(null);
        }
        // RAFRAÎCHIT : la présence d'activité utilisateur met à jour le TTL
        const wtx = db.transaction(STORE, 'readwrite');
        wtx.objectStore(STORE).put({ ...rec, saved_at: Date.now() }, ENTRY_ID);
        resolve(rec.key);
      };
      req.onerror = () => reject(req.error);
    });
  }

  /**
   * Entre la page de connexion et la page du code (2FA), la clé de compte dérivée
   * du mot de passe doit survivre au changement de page. Elle est gardée comme
   * CryptoKey AES NON EXPORTABLE, 5 minutes au plus, et lue une seule fois.
   */
  const PENDING_ID = 'pending-account-key';
  const PENDING_TTL_MS = 5 * 60 * 1000;

  async function savePending(aesKey) {
    const db = await openDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.objectStore(STORE).put({ key: aesKey, saved_at: Date.now() }, PENDING_ID);
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => reject(tx.error);
    });
  }

  async function takePending() {
    const db = await openDB();
    return new Promise((resolve) => {
      const tx = db.transaction(STORE, 'readwrite');
      const st = tx.objectStore(STORE);
      const req = st.get(PENDING_ID);
      req.onsuccess = () => {
        const rec = req.result;
        st.delete(PENDING_ID);
        resolve(rec && Date.now() - rec.saved_at <= PENDING_TTL_MS ? rec.key : null);
      };
      req.onerror = () => resolve(null);
    });
  }

  /** Efface la clé privée de IndexedDB (déconnexion, inactivité...). */
  async function clear() {
    const db = await openDB();
    return new Promise((resolve) => {
      const tx = db.transaction(STORE, 'readwrite');
      tx.objectStore(STORE).delete(PENDING_ID);
      const req = tx.objectStore(STORE).delete(ENTRY_ID);
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => resolve(false);
    });
  }

  /** Met à jour l'horodatage d'activité sans relire la clé. */
  async function touch() {
    const db = await openDB();
    return new Promise((resolve) => {
      const tx = db.transaction(STORE, 'readwrite');
      const st = tx.objectStore(STORE);
      const req = st.get(ENTRY_ID);
      req.onsuccess = () => {
        const rec = req.result;
        if (rec && Date.now() - rec.saved_at <= VAULT_INACTIVITY_MS) {
          st.put({ ...rec, saved_at: Date.now() }, ENTRY_ID);
        }
      };
      tx.oncomplete = () => resolve(true);
      tx.onerror = () => resolve(false);
    });
  }

  return { save, load, clear, touch, savePending, takePending };
})();

// ── Écouteurs globaux de purge à l'inactivité ─────────────────

let _purgeTimer = null;
let _lastTouch = 0;
function _schedulePurge() {
  // L'activité de l'utilisateur prolonge la durée de vie de la clé (au plus une écriture / 30 s)
  if (Date.now() - _lastTouch > 30000) {
    _lastTouch = Date.now();
    VaultKeyStore.touch().catch(() => {});
  }
  clearTimeout(_purgeTimer);
  _purgeTimer = setTimeout(async () => {
    await VaultKeyStore.clear();
  }, VAULT_INACTIVITY_MS);
}

['mousemove', 'keydown', 'click', 'scroll', 'touchstart'].forEach(evt => {
  document.addEventListener(evt, _schedulePurge, { passive: true });
  window.addEventListener(evt, _schedulePurge, { passive: true });
});
_schedulePurge();

// Remarque : pas de purge sur "beforeunload". Cet événement se déclenche à
// CHAQUE changement de page de l'application (tableau de bord -> upload...),
// ce qui effaçait la clé et obligeait à se reconnecter en permanence.
// La clé est effacée à la déconnexion et après 10 minutes d'inactivité.

// Appelé par logout.html avant redirection
window.vaultLogoutPurge = async function () {
  await VaultKeyStore.clear();
};

// Déconnexion : la clé est effacée du navigateur AVANT de quitter la page.
document.addEventListener('click', async (e) => {
  const link = e.target.closest ? e.target.closest('a[href="/logout"]') : null;
  if (!link) return;
  e.preventDefault();
  try { await VaultKeyStore.clear(); } catch (err) { /* ignore */ }
  window.location.replace('/logout');
});
