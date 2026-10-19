/**
 * vault-umbral.js — Chargement de la bibliothèque Umbral (umbral-pre 0.10.0,
 * implémentation Rust de référence compilée en WebAssembly, servie par Vault).
 * Expose window.Umbral et l'événement « umbral-ready ».
 */
import * as bg from './umbral/umbral_pre_wasm_bg.js';

const resp = await fetch('/static/js/umbral/umbral_pre_wasm_bg.wasm', { credentials: 'same-origin' });
const { instance } = await WebAssembly.instantiate(await resp.arrayBuffer(),
  { './umbral_pre_wasm_bg.js': bg });
bg.__wbg_set_wasm(instance.exports);
window.Umbral = bg;
window.dispatchEvent(new Event('umbral-ready'));
