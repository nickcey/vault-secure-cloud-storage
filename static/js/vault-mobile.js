/**
 * vault-mobile.js — Vault sur téléphone : barre d'onglets en bas de l'écran.
 *
 * Fichiers · Partagés · molette « + » (téléverser) · Corbeille · Plus.
 * « Plus » ouvre une feuille avec le compte, l'espace utilisé et les autres pages.
 * Ne s'active que sur les pages de l'application (données #vaultMe fournies par le
 * serveur) ; l'affichage n'apparaît que sous 768 px (vault-mobile-app.css).
 */
(function () {
  'use strict';
  const data = document.getElementById('vaultMe');
  if (!data) return;
  let me;
  try { me = JSON.parse(data.textContent); } catch (e) { return; }

  const P = 'xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" aria-hidden="true"';
  const ICON = {
    files: `<svg ${P}><path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2.5h7.5A2.5 2.5 0 0 1 21 10v7.5a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/></svg>`,
    shared: `<svg ${P}><circle cx="9" cy="8.5" r="3.2"/><path d="M3.5 19c.7-3 3-4.6 5.5-4.6s4.8 1.6 5.5 4.6"/><circle cx="17" cy="9.5" r="2.5"/><path d="M16 14.6c2.3.1 3.9 1.5 4.5 3.9"/></svg>`,
    plus: `<svg ${P}><path d="M12 5.5v13M5.5 12h13"/></svg>`,
    trash: `<svg ${P}><path d="M4.5 7h15M10 4h4M6.5 7l.9 12a1.8 1.8 0 0 0 1.8 1.6h5.6a1.8 1.8 0 0 0 1.8-1.6l.9-12M10 11v6M14 11v6"/></svg>`,
    more: `<svg ${P}><circle cx="5.5" cy="12" r="1.3"/><circle cx="12" cy="12" r="1.3"/><circle cx="18.5" cy="12" r="1.3"/></svg>`,
    link: `<svg ${P}><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/></svg>`,
    shield: `<svg ${P}><path d="M12 3.5 5 6v5.5c0 4.4 3 7.7 7 9 4-1.3 7-4.6 7-9V6z"/><path d="m9 12 2 2 4-4"/></svg>`,
    activity: `<svg ${P}><path d="M3.5 12h4l2.5-6 4 12 2.5-6h4"/></svg>`,
    devices: `<svg ${P}><rect x="3" y="5" width="13" height="10" rx="1.6"/><path d="M7 19h5"/><rect x="17.5" y="9" width="4" height="10" rx="1"/></svg>`,
    settings: `<svg ${P}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.6 1.6 0 0 0-1-1.5 1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.6 1.6 0 0 0 1.5-1 1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1z"/></svg>`,
    star: `<svg ${P}><path d="m12 3.8 2.5 5.1 5.6.8-4 4 .9 5.6-5-2.7-5 2.7.9-5.6-4-4 5.6-.8z"/></svg>`,
    moon: `<svg ${P}><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/></svg>`,
    globe: `<svg ${P}><circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.4 2.4 3.5 5.3 3.5 8.5s-1.1 6.1-3.5 8.5c-2.4-2.4-3.5-5.3-3.5-8.5S9.6 5.9 12 3.5z"/></svg>`,
    crown: `<svg ${P}><path d="m4 8 4 4 4-6 4 6 4-4-1.5 10h-13z"/></svg>`,
    out: `<svg ${P}><path d="M14 4h3.5A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5H14M10 16l-4-4 4-4M6 12h10"/></svg>`,
  };
  const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const path = location.pathname;
  const is = (...ps) => ps.some(p => path === p || path.startsWith(p + '/'));

  // La molette téléverse dans le dossier ouvert, s'il y en a un
  const folder = new URLSearchParams(location.search).get('folder');
  const uploadHref = '/upload' + (folder && is('/dashboard') ? '?folder=' + encodeURIComponent(folder) : '');

  function build() {
    document.body.classList.add('vm-app');

    const bar = document.createElement('nav');
    bar.id = 'vaultTabbar';
    bar.setAttribute('aria-label', 'Navigation');
    const moreActive = !is('/dashboard', '/shared-with-me', '/trash', '/trash-page', '/upload', '/upload-page');
    bar.innerHTML =
      `<a class="vm-tab${is('/dashboard') ? ' active' : ''}" href="/dashboard">${ICON.files}<span>Fichiers</span></a>` +
      `<a class="vm-tab${is('/shared-with-me') ? ' active' : ''}" href="/shared-with-me">${ICON.shared}<span>Partagés</span></a>` +
      `<a class="vm-dial${is('/upload', '/upload-page') ? ' active' : ''}" href="${uploadHref}" aria-label="Téléverser">${ICON.plus}</a>` +
      `<a class="vm-tab${is('/trash', '/trash-page') ? ' active' : ''}" href="/trash">${ICON.trash}<span>Corbeille</span></a>` +
      `<button type="button" class="vm-tab${moreActive ? ' active' : ''}" id="vmMoreBtn" aria-haspopup="dialog">${ICON.more}<span>Plus</span></button>`;

    const backdrop = document.createElement('div');
    backdrop.className = 'vm-backdrop';

    const light = () => document.body.classList.contains('light') || document.documentElement.classList.contains('light');
    const sheet = document.createElement('section');
    sheet.id = 'vaultMoreSheet';
    sheet.setAttribute('role', 'dialog');
    sheet.setAttribute('aria-label', 'Plus');
    const item = (href, icon, label, cls = '', val = '') =>
      `<li><a href="${href}" class="${cls}">${ICON[icon]}<span>${label}</span>${val ? `<span class="vm-val">${val}</span>` : ''}</a></li>`;
    sheet.innerHTML =
      `<div class="vm-handle"></div>
       <div class="vm-me" translate="no"><div class="vm-avatar">${esc((me.name || '?')[0].toUpperCase())}</div>
         <div><div class="vm-me-name">${esc(me.name)}</div><div class="vm-me-mail">${esc(me.email)}</div></div></div>
       <div class="vm-storage">
         <div class="vm-storage-top"><span><b>${esc(me.used)}</b> utilisés sur ${esc(me.total)}</span><a href="/plans">${esc(String(me.plan).toUpperCase())}</a></div>
         <div class="vm-bar"><span style="width:${Math.max(1.5, +me.percent || 0)}%"></span></div>
       </div>
       <ul class="vm-list">
         ${item('/transfers', 'link', 'Mes liens de partage')}
         ${item('/trusted-contacts', 'shield', 'Contacts de confiance')}
         ${item('/activity', 'activity', 'Activité')}
         ${item('/sessions', 'devices', 'Sessions')}
         ${item('/settings', 'settings', 'Paramètres')}
         ${item('/plans', 'star', 'Abonnement')}
         <li><button type="button" id="vmTheme">${ICON.moon}<span>Thème</span><span class="vm-val" id="vmThemeVal"></span></button></li>
         ${item('/set_language/' + (me.lang === 'en' ? 'fr' : 'en'), 'globe', 'Langue', '', me.lang === 'en' ? 'English' : 'Français')}
         ${me.admin ? item('/admin', 'crown', 'Administration') : ''}
         ${item('/logout', 'out', 'Déconnexion', 'vm-danger')}
       </ul>`;

    document.body.append(backdrop, sheet, bar);

    const themeVal = sheet.querySelector('#vmThemeVal');
    const showTheme = () => { themeVal.textContent = light() ? 'Clair' : 'Sombre'; };
    showTheme();
    sheet.querySelector('#vmTheme').addEventListener('click', () => {
      if (typeof window.toggleTheme === 'function') window.toggleTheme();
      setTimeout(showTheme, 50);
    });

    const open = () => { sheet.classList.add('open'); backdrop.classList.add('show'); };
    const close = () => { sheet.classList.remove('open'); backdrop.classList.remove('show'); };
    bar.querySelector('#vmMoreBtn').addEventListener('click', open);
    backdrop.addEventListener('click', close);
    document.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });

    // L'avatar du tableau de bord ouvre aussi la feuille « Plus »
    const avatar = document.querySelector('.topbar .user-menu');
    if (avatar) avatar.addEventListener('click', e => {
      if (window.matchMedia('(max-width: 768px)').matches) { e.preventDefault(); e.stopPropagation(); open(); }
    }, true);

    // Menu d'un fichier : affiché comme une feuille d'actions au-dessus de tout.
    // Il est déplacé le temps de son ouverture (ses boutons gardent leurs actions),
    // puis remis à sa place.
    const host = document.createElement('div');
    host.id = 'vmActionHost';
    document.body.appendChild(host);
    const actionBackdrop = document.createElement('div');
    actionBackdrop.className = 'vm-backdrop';
    actionBackdrop.style.zIndex = '955';
    document.body.appendChild(actionBackdrop);
    let moved = null;   // { menu, parent, next }
    const mobile = () => window.matchMedia('(max-width: 768px)').matches;
    function restore() {
      if (!moved) return;
      const { menu, parent, next } = moved;
      moved = null;
      menu.classList.remove('open');
      if (parent.isConnected) parent.insertBefore(menu, next && next.parentNode === parent ? next : null);
      else menu.remove();
      document.querySelectorAll('tr.menu-open').forEach(r => r.classList.remove('menu-open'));
      actionBackdrop.classList.remove('show');
    }
    new MutationObserver(recs => {
      if (!mobile()) return;
      for (const r of recs) {
        const m = r.target;
        if (!m.classList || !m.classList.contains('dropdown-menu')) continue;
        if (m.classList.contains('open') && m.parentNode !== host) {
          restore();
          moved = { menu: m, parent: m.parentNode, next: m.nextSibling };
          host.appendChild(m);
          actionBackdrop.classList.add('show');
        } else if (!m.classList.contains('open') && moved && moved.menu === m) {
          restore();
        }
      }
    }).observe(document.body, { attributes: true, attributeFilter: ['class'], subtree: true });
    actionBackdrop.addEventListener('click', restore);
    host.addEventListener('click', e => { if (e.target.closest('.dropdown-item')) setTimeout(restore, 0); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build);
  else build();
})();
