/**
 * vault-shamir.js — Partage de secret de Shamir (seuil k sur n, 3 sur 5 dans Vault) sur GF(2^8)
 * et récupération de compte par contacts de confiance.
 *
 * Un secret S de 32 octets est découpé octet par octet avec un polynôme de
 * degré k-1 tiré au hasard (terme constant = octet secret). Vault utilise
 * n = 5 parts et un seuil k = 3 : trois parts quelconques retrouvent S par
 * interpolation de Lagrange en 0 ; deux parts ne donnent aucune information sur S.
 */
(function () {
  'use strict';

  // ── Corps GF(2^8), polynôme irréductible x^8 + x^4 + x^3 + x + 1 (0x11b), générateur 3 ──
  const EXP = new Uint8Array(510), LOG = new Uint8Array(256);
  (function () {
    let x = 1;
    for (let i = 0; i < 255; i++) {
      EXP[i] = x; LOG[x] = i;
      let y = x << 1; if (y & 0x100) y ^= 0x11b;   // x·2
      x = y ^ x;                                    // x·3
    }
    for (let i = 255; i < 510; i++) EXP[i] = EXP[i - 255];
  })();
  const mul = (a, b) => (a === 0 || b === 0) ? 0 : EXP[LOG[a] + LOG[b]];
  const div = (a, b) => { if (b === 0) throw new Error('division par zéro'); return a === 0 ? 0 : EXP[(LOG[a] + 255 - LOG[b]) % 255]; };

  /**
   * Découpe secret (Uint8Array) en n parts d'abscisses 1..n ; k parts suffisent.
   * Pour chaque octet : polynôme de degré k-1 dont le terme constant est l'octet secret.
   */
  function split(secret, n, k) {
    n = n || 5; k = k || 3;
    if (k < 2 || k > n || n > 255) throw new Error('Paramètres de partage invalides');
    const coefs = [];
    for (let d = 1; d < k; d++) coefs.push(crypto.getRandomValues(new Uint8Array(secret.length)));
    const shares = {};
    for (let x = 1; x <= n; x++) {
      const y = new Uint8Array(secret.length);
      for (let i = 0; i < secret.length; i++) {
        // Horner : a_{k-1}·x^{k-1} + ... + a_1·x + s
        let acc = 0;
        for (let d = coefs.length - 1; d >= 0; d--) acc = mul(acc ^ coefs[d][i], x);
        y[i] = acc ^ secret[i];
      }
      shares[x] = y;
    }
    coefs.forEach(c => c.fill(0));
    return shares;
  }

  /** Reconstitue le secret à partir de k parts {x, y} (interpolation de Lagrange en 0). */
  function combine(parts) {
    if (parts.length < 2) throw new Error('Pas assez de parts');
    const xs = parts.map(p => p.x);
    if (new Set(xs).size !== xs.length) throw new Error('Parts en double');
    const out = new Uint8Array(parts[0].y.length);
    parts.forEach((pj, j) => {
      // l_j(0) = Π_{m≠j} x_m / (x_m ⊕ x_j)
      let l = 1;
      parts.forEach((pm, m) => { if (m !== j) l = mul(l, div(pm.x, pm.x ^ pj.x)); });
      for (let i = 0; i < out.length; i++) out[i] ^= mul(pj.y[i], l);
    });
    return out;
  }

  /** Clé de chiffrement et preuve d'authentification dérivées du secret (HKDF, usages séparés). */
  async function deriveFromSecret(secret) {
    const base = await crypto.subtle.importKey('raw', secret, 'HKDF', false, ['deriveBits']);
    const d = async info => new Uint8Array(await crypto.subtle.deriveBits(
      { name: 'HKDF', hash: 'SHA-256', salt: new Uint8Array(0), info: strToBuf(info) }, base, 256));
    return { key: await d('vault-shamir-key-v1'), auth: await d('vault-shamir-auth-v1') };
  }

  window.VaultShamir = { split, combine, deriveFromSecret, _mul: mul };
})();
