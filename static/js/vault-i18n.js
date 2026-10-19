/**
 * vault-i18n.js — Interface en anglais.
 *
 * Les pages et les scripts de Vault sont écrits en français. Quand la langue choisie
 * est l'anglais (<html lang="en">), ce script traduit tout ce qui s'affiche, avec le
 * dictionnaire chargé juste avant (/i18n/en.js, le même que pour les courriels) :
 *   - le texte des pages et les attributs visibles (placeholder, title, aria-label…) ;
 *   - ce que les scripts ajoutent ensuite (MutationObserver) : messages, listes, erreurs
 *     renvoyées par le serveur ;
 *   - les boîtes de dialogue alert / confirm / prompt.
 * Les noms de fichiers et de dossiers ne sont jamais touchés : seules les phrases connues
 * sont remplacées. Les éléments marqués translate="no" sont ignorés.
 */
(function () {
  'use strict';
  const root = document.documentElement;
  if (root.lang !== 'en' || !window.VAULT_EN) return;
  const D = window.VAULT_EN;

  // Page masquée jusqu'à la première traduction (pas de clignotement du français)
  root.style.visibility = 'hidden';
  const reveal = () => { root.style.visibility = ''; };
  setTimeout(reveal, 1500);   // sécurité : jamais de page blanche

  const phrases = new Map(Object.entries(D.phrases));
  const patterns = D.patterns.map(([src, repl]) => [new RegExp('^' + src + '$', 'su'), repl]);
  const inline = D.inline.map(([src, repl]) => [new RegExp(src, 'gu'), repl]);
  const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const fragKeys = [...phrases.keys()].filter(k => k.includes(' ') && k.length >= 8).sort((a, b) => b.length - a.length);
  const frag = fragKeys.length
    ? new RegExp('(?<![\\p{L}\\p{N}_])(' + fragKeys.map(esc).join('|') + ')(?![\\p{L}\\p{N}_])', 'gu') : null;

  function fill(repl, m, depth) {
    return repl.replace(/([$]|\{)(\d)\}?/g, (_, kind, i) => {
      const v = m[+i] || '';
      return kind === '$' ? v : core(v, depth + 1);
    });
  }
  function core(s, depth = 0) {
    if (!s || depth > 3) return s;
    const hit = phrases.get(s);
    if (hit !== undefined) return hit;
    for (const [rx, repl] of patterns) {
      const m = s.match(rx);
      if (m) return fill(repl, m, depth);
    }
    return frag ? s.replace(frag, k => phrases.get(k)) : s;
  }
  /** Traduit un texte (plusieurs lignes possibles), en gardant les espaces autour. */
  function tr(text) {
    if (!text || !/[A-Za-zÀ-ÿ]/.test(text)) return text;
    return String(text).split('\n').map(line => {
      const c = line.replace(/\s+/g, ' ').trim();
      if (!c) return line;
      let out = core(c);
      for (const [rx, repl] of inline) out = out.replace(rx, repl);
      if (out === c) return line;
      const lead = line.match(/^\s*/)[0], trail = line.match(/\s*$/)[0];
      return lead + out + trail;
    }).join('\n');
  }
  window.vaultT = tr;

  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEXTAREA', 'CODE', 'PRE']);
  const ATTRS = ['placeholder', 'title', 'aria-label', 'alt'];
  // Noms choisis par l'utilisateur (fichiers, dossiers) : jamais traduits
  const KEEP = '[translate="no"], .notranslate, .file-name-text, .file-name, .fh-name, .crumb-current:not(:first-child), #folderBreadcrumb a:not(:first-child)';
  const skipped = el => !el || SKIP.has(el.tagName) || !!el.closest(KEEP);

  function doText(node) {
    if (skipped(node.parentElement)) return;
    const v = node.nodeValue, t = tr(v);
    if (t !== v) node.nodeValue = t;
  }
  function doAttrs(el) {
    if (skipped(el)) return;
    for (const a of ATTRS) {
      const v = el.getAttribute(a);
      if (v) { const t = tr(v); if (t !== v) el.setAttribute(a, t); }
    }
    if (el.tagName === 'INPUT' && /^(submit|button|reset)$/.test(el.type) && el.value) {
      const t = tr(el.value); if (t !== el.value) el.value = t;
    }
  }
  function walk(rootNode) {
    if (rootNode.nodeType === 3) return doText(rootNode);
    if (rootNode.nodeType !== 1 && rootNode.nodeType !== 9) return;
    if (rootNode.nodeType === 1) { if (skipped(rootNode)) return; doAttrs(rootNode); }
    const w = document.createTreeWalker(rootNode, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    let n;
    while ((n = w.nextNode())) n.nodeType === 3 ? doText(n) : doAttrs(n);
  }

  new MutationObserver(records => {
    for (const r of records) {
      if (r.type === 'childList') r.addedNodes.forEach(walk);
      else if (r.type === 'characterData') doText(r.target);
      else if (r.type === 'attributes') doAttrs(r.target);
    }
  }).observe(root, { childList: true, subtree: true, characterData: true,
                     attributes: true, attributeFilter: ATTRS.concat('value') });

  document.addEventListener('DOMContentLoaded', () => {
    walk(document);
    document.title = tr(document.title);
    reveal();
  });

  // Boîtes de dialogue du navigateur
  const _alert = window.alert.bind(window), _confirm = window.confirm.bind(window), _prompt = window.prompt.bind(window);
  window.alert = m => _alert(tr(String(m ?? '')));
  window.confirm = m => _confirm(tr(String(m ?? '')));
  window.prompt = (m, d) => _prompt(tr(String(m ?? '')), d);
})();
