/* Vault — service worker minimal : il permet d'installer Vault comme une application
   (fenêtre avec le logo et le nom Vault). Il ne met rien en cache et ne modifie aucune
   requête : tout continue de passer directement par le réseau. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
