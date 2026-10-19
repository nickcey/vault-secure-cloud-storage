/**
 * vault-icons.js — Icônes de fichiers (même table que utils/file_icons.py).
 * Le serveur ne connaît plus les noms de fichiers : l'icône est choisie
 * dans le navigateur, une fois le nom déchiffré.
 */
(function () {
  'use strict';
  const ICONS = {
"pdf": {
"path": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M9 13h6 M9 17h6 M9 9h1",
"viewbox": "0 0 24 24",
"color": "#ff3b44",
"glow": "rgba(255,59,68,0.5)",
"bg_color": "rgba(74,158,255,0.10)",
"category": "document"
},
"doc": {
"path": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8",
"viewbox": "0 0 24 24",
"color": "#4a9eff",
"glow": "rgba(74,158,255,0.5)",
"bg_color": "rgba(74,158,255,0.10)",
"category": "document"
},
"docx": {
"path": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8 M10 9H8",
"viewbox": "0 0 24 24",
"color": "#4a9eff",
"glow": "rgba(74,158,255,0.5)",
"bg_color": "rgba(74,158,255,0.10)",
"category": "document"
},
"txt": {
"path": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8",
"viewbox": "0 0 24 24",
"color": "#f3e6e4",
"glow": "rgba(243,230,228,0.4)",
"bg_color": "rgba(74,158,255,0.10)",
"category": "document"
},
"md": {
"path": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M10 13l2 2 4-4",
"viewbox": "0 0 24 24",
"color": "#f3e6e4",
"glow": "rgba(243,230,228,0.4)",
"bg_color": "rgba(74,158,255,0.10)",
"category": "document"
},
"csv": {
"path": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 13h8 M8 17h5 M11 9H8",
"viewbox": "0 0 24 24",
"color": "#4ade80",
"glow": "rgba(74,222,128,0.5)",
"bg_color": "rgba(74,158,255,0.10)",
"category": "document"
},
"xls": {
"path": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 10v8 M12 10v8 M16 10v8 M8 14h8",
"viewbox": "0 0 24 24",
"color": "#22c55e",
"glow": "rgba(34,197,94,0.5)",
"bg_color": "rgba(74,158,255,0.10)",
"category": "document"
},
"xlsx": {
"path": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 10v8 M12 10v8 M16 10v8 M8 14h8",
"viewbox": "0 0 24 24",
"color": "#22c55e",
"glow": "rgba(34,197,94,0.5)",
"bg_color": "rgba(74,158,255,0.10)",
"category": "document"
},
"ppt": {
"path": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 10h4v2H8z M8 14h8",
"viewbox": "0 0 24 24",
"color": "#f97316",
"glow": "rgba(249,115,22,0.5)",
"bg_color": "rgba(74,158,255,0.10)",
"category": "document"
},
"pptx": {
"path": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 10h4v2H8z M8 14h8",
"viewbox": "0 0 24 24",
"color": "#f97316",
"glow": "rgba(249,115,22,0.5)",
"bg_color": "rgba(74,158,255,0.10)",
"category": "document"
},
"odt": {
"path": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8",
"viewbox": "0 0 24 24",
"color": "#4a9eff",
"glow": "rgba(74,158,255,0.5)",
"bg_color": "rgba(74,158,255,0.10)",
"category": "document"
},
"rtf": {
"path": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8 M16 17H8",
"viewbox": "0 0 24 24",
"color": "#f3e6e4",
"glow": "rgba(243,230,228,0.4)",
"bg_color": "rgba(74,158,255,0.10)",
"category": "document"
},
"jpg": {
"path": "M21 19V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2z M8.5 13.5l2.5 3 3.5-4.5 4.5 6H5",
"viewbox": "0 0 24 24",
"color": "#a855f7",
"glow": "rgba(168,85,247,0.5)",
"bg_color": "rgba(168,85,247,0.10)",
"category": "image"
},
"jpeg": {
"path": "M21 19V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2z M8.5 13.5l2.5 3 3.5-4.5 4.5 6H5",
"viewbox": "0 0 24 24",
"color": "#a855f7",
"glow": "rgba(168,85,247,0.5)",
"bg_color": "rgba(168,85,247,0.10)",
"category": "image"
},
"png": {
"path": "M21 19V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2z M8.5 13.5l2.5 3 3.5-4.5 4.5 6H5",
"viewbox": "0 0 24 24",
"color": "#a855f7",
"glow": "rgba(168,85,247,0.5)",
"bg_color": "rgba(168,85,247,0.10)",
"category": "image"
},
"gif": {
"path": "M21 19V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2z M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
"viewbox": "0 0 24 24",
"color": "#d946ef",
"glow": "rgba(217,70,239,0.5)",
"bg_color": "rgba(168,85,247,0.10)",
"category": "image"
},
"webp": {
"path": "M21 19V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2z M8.5 13.5l2.5 3 3.5-4.5 4.5 6H5",
"viewbox": "0 0 24 24",
"color": "#a855f7",
"glow": "rgba(168,85,247,0.5)",
"bg_color": "rgba(168,85,247,0.10)",
"category": "image"
},
"bmp": {
"path": "M21 19V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2z M8.5 13.5l2.5 3 3.5-4.5 4.5 6H5",
"viewbox": "0 0 24 24",
"color": "#a855f7",
"glow": "rgba(168,85,247,0.5)",
"bg_color": "rgba(168,85,247,0.10)",
"category": "image"
},
"ico": {
"path": "M21 19V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2z M12 8l-3 5h6l-3-5z",
"viewbox": "0 0 24 24",
"color": "#a855f7",
"glow": "rgba(168,85,247,0.5)",
"bg_color": "rgba(168,85,247,0.10)",
"category": "image"
},
"tiff": {
"path": "M21 19V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2z M8.5 13.5l2.5 3 3.5-4.5 4.5 6H5",
"viewbox": "0 0 24 24",
"color": "#a855f7",
"glow": "rgba(168,85,247,0.5)",
"bg_color": "rgba(168,85,247,0.10)",
"category": "image"
},
"tif": {
"path": "M21 19V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2z M8.5 13.5l2.5 3 3.5-4.5 4.5 6H5",
"viewbox": "0 0 24 24",
"color": "#a855f7",
"glow": "rgba(168,85,247,0.5)",
"bg_color": "rgba(168,85,247,0.10)",
"category": "image"
},
"zip": {
"path": "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z M3.27 6.96L12 12.01l8.73-5.05M12 22.08V12",
"viewbox": "0 0 24 24",
"color": "#f59e0b",
"glow": "rgba(245,158,11,0.5)",
"bg_color": "rgba(245,158,11,0.10)",
"category": "archive"
},
"rar": {
"path": "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z M3.27 6.96L12 12.01l8.73-5.05M12 22.08V12",
"viewbox": "0 0 24 24",
"color": "#f59e0b",
"glow": "rgba(245,158,11,0.5)",
"bg_color": "rgba(245,158,11,0.10)",
"category": "archive"
},
"7z": {
"path": "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z M3.27 6.96L12 12.01l8.73-5.05M12 22.08V12",
"viewbox": "0 0 24 24",
"color": "#f59e0b",
"glow": "rgba(245,158,11,0.5)",
"bg_color": "rgba(245,158,11,0.10)",
"category": "archive"
},
"tar": {
"path": "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z M3.27 6.96L12 12.01l8.73-5.05M12 22.08V12",
"viewbox": "0 0 24 24",
"color": "#f59e0b",
"glow": "rgba(245,158,11,0.5)",
"bg_color": "rgba(245,158,11,0.10)",
"category": "archive"
},
"gz": {
"path": "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z M3.27 6.96L12 12.01l8.73-5.05M12 22.08V12",
"viewbox": "0 0 24 24",
"color": "#f59e0b",
"glow": "rgba(245,158,11,0.5)",
"bg_color": "rgba(245,158,11,0.10)",
"category": "archive"
},
"mp3": {
"path": "M9 18V5l12-2v13M9 18c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3 3 1.34 3 3zm12-2c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3 3 1.34 3 3z",
"viewbox": "0 0 24 24",
"color": "#ec4899",
"glow": "rgba(236,72,153,0.5)",
"bg_color": "rgba(236,72,153,0.10)",
"category": "audio"
},
"wav": {
"path": "M9 18V5l12-2v13M9 18c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3 3 1.34 3 3zm12-2c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3 3 1.34 3 3z",
"viewbox": "0 0 24 24",
"color": "#ec4899",
"glow": "rgba(236,72,153,0.5)",
"bg_color": "rgba(236,72,153,0.10)",
"category": "audio"
},
"ogg": {
"path": "M9 18V5l12-2v13M9 18c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3 3 1.34 3 3zm12-2c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3 3 1.34 3 3z",
"viewbox": "0 0 24 24",
"color": "#ec4899",
"glow": "rgba(236,72,153,0.5)",
"bg_color": "rgba(236,72,153,0.10)",
"category": "audio"
},
"flac": {
"path": "M9 18V5l12-2v13M9 18c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3 3 1.34 3 3zm12-2c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3 3 1.34 3 3z",
"viewbox": "0 0 24 24",
"color": "#ec4899",
"glow": "rgba(236,72,153,0.5)",
"bg_color": "rgba(236,72,153,0.10)",
"category": "audio"
},
"m4a": {
"path": "M9 18V5l12-2v13M9 18c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3 3 1.34 3 3zm12-2c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3 3 1.34 3 3z",
"viewbox": "0 0 24 24",
"color": "#ec4899",
"glow": "rgba(236,72,153,0.5)",
"bg_color": "rgba(236,72,153,0.10)",
"category": "audio"
},
"aac": {
"path": "M9 18V5l12-2v13M9 18c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3 3 1.34 3 3zm12-2c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3 3 1.34 3 3z",
"viewbox": "0 0 24 24",
"color": "#ec4899",
"glow": "rgba(236,72,153,0.5)",
"bg_color": "rgba(236,72,153,0.10)",
"category": "audio"
},
"wma": {
"path": "M9 18V5l12-2v13M9 18c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3 3 1.34 3 3zm12-2c0 1.66-1.34 3-3 3s-3-1.34-3-3 1.34-3 3-3 3 1.34 3 3z",
"viewbox": "0 0 24 24",
"color": "#ec4899",
"glow": "rgba(236,72,153,0.5)",
"bg_color": "rgba(236,72,153,0.10)",
"category": "audio"
},
"mp4": {
"path": "M23 7l-7 5 7 5V7zM1 5v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1z",
"viewbox": "0 0 24 24",
"color": "#ef4444",
"glow": "rgba(239,68,68,0.5)",
"bg_color": "rgba(239,68,68,0.10)",
"category": "video"
},
"avi": {
"path": "M23 7l-7 5 7 5V7zM1 5v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1z",
"viewbox": "0 0 24 24",
"color": "#ef4444",
"glow": "rgba(239,68,68,0.5)",
"bg_color": "rgba(239,68,68,0.10)",
"category": "video"
},
"mkv": {
"path": "M23 7l-7 5 7 5V7zM1 5v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1z",
"viewbox": "0 0 24 24",
"color": "#ef4444",
"glow": "rgba(239,68,68,0.5)",
"bg_color": "rgba(239,68,68,0.10)",
"category": "video"
},
"mov": {
"path": "M23 7l-7 5 7 5V7zM1 5v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1z",
"viewbox": "0 0 24 24",
"color": "#ef4444",
"glow": "rgba(239,68,68,0.5)",
"bg_color": "rgba(239,68,68,0.10)",
"category": "video"
},
"wmv": {
"path": "M23 7l-7 5 7 5V7zM1 5v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1z",
"viewbox": "0 0 24 24",
"color": "#ef4444",
"glow": "rgba(239,68,68,0.5)",
"bg_color": "rgba(239,68,68,0.10)",
"category": "video"
},
"flv": {
"path": "M23 7l-7 5 7 5V7zM1 5v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1z",
"viewbox": "0 0 24 24",
"color": "#ef4444",
"glow": "rgba(239,68,68,0.5)",
"bg_color": "rgba(239,68,68,0.10)",
"category": "video"
},
"webm": {
"path": "M23 7l-7 5 7 5V7zM1 5v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1z",
"viewbox": "0 0 24 24",
"color": "#ef4444",
"glow": "rgba(239,68,68,0.5)",
"bg_color": "rgba(239,68,68,0.10)",
"category": "video"
},
"mpeg": {
"path": "M23 7l-7 5 7 5V7zM1 5v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1z",
"viewbox": "0 0 24 24",
"color": "#ef4444",
"glow": "rgba(239,68,68,0.5)",
"bg_color": "rgba(239,68,68,0.10)",
"category": "video"
},
"mpg": {
"path": "M23 7l-7 5 7 5V7zM1 5v14a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V5a1 1 0 0 0-1-1H2a1 1 0 0 0-1 1z",
"viewbox": "0 0 24 24",
"color": "#ef4444",
"glow": "rgba(239,68,68,0.5)",
"bg_color": "rgba(239,68,68,0.10)",
"category": "video"
},
"py": {
"path": "M9.585 11.692h4.328s2.432.039 2.432-2.35V5.391S16.714 3 11.936 3C7.362 3 7.647 4.983 7.647 4.983l.006 2.055h4.363v.617H5.92s-2.927-.332-2.927 4.282 2.555 4.45 2.555 4.45h1.524v-2.141s-.083-2.554 2.513-2.554zm-.056-5.74a.784.784 0 1 1 0-1.57.784.784 0 0 1 0 1.57z M14.415 12.308h-4.328s-2.432-.04-2.432 2.35v3.951s-.369 2.391 4.409 2.391c4.573 0 4.288-1.983 4.288-1.983l-.006-2.055h-4.363v-.617h6.097s2.927.332 2.927-4.282-2.555-4.45-2.555-4.45h-1.524v2.141s.083 2.554-2.513 2.554zm.056 5.74a.784.784 0 1 1 0 1.57.784.784 0 0 1 0-1.57z",
"viewbox": "0 0 24 24",
"color": "#facc15",
"glow": "rgba(250,204,21,0.5)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"java": {
"path": "M11.622 19.955c0 0-1.029.599 .731.802 2.139.244 3.23.209 5.587-.237 0 0 .619.387 1.483.722-5.273 2.26-11.936-.131-7.801-1.287zM10.934 17.356c0 0-1.155.855 .606 1.038 2.277.236 4.077.256 7.189-.347 0 0 .431.436 1.107.674-6.357 1.859-13.437.146-8.902-1.365zM15.019 11.813c1.299 1.495-.341 2.839-.341 2.839s3.296-1.703 1.782-3.836c-1.411-1.989-2.493-2.977 3.368-6.382 0 0-9.207 2.299-4.809 7.379zM20.178 21.477c0 0 .762.629-0.838 1.116-3.04.924-12.659 1.202-15.331.037-.961-.419.841-.998 1.408-1.12.592-.127.93-.104.93-.104-1.07-.754-6.906 1.477-2.965 2.116 10.742 1.741 19.586-.784 16.796-2.045zM11.988 14.055c0 0-4.894 1.162-1.733 1.584 1.337.178 4.001.138 6.487-.07 2.033-.171 4.071-.535 4.071-.535s-.716.307-1.235.66c-4.969 1.307-14.569.698-11.808-.638 2.329-1.126 4.218-.999 4.218-.999zM18.352 18.711c5.05-2.624 2.714-5.148 1.085-4.809-.399.083-.577.155-.577.155s.148-.231.431-.331c3.22-1.132 5.696 3.345-1.039 5.118 0 0 .078-.07.1-.133zM14.939 3c0 0 2.797 2.797-2.653 7.089-4.367 3.442-.997 5.404-.001 7.646-2.543-2.295-4.407-4.314-3.156-6.196 1.84-2.766 6.929-4.106 5.81-8.539zM12.184 23.973c4.849.31 12.297-.172 12.477-2.464 0 0-.339.871-4.011 1.561-4.138.777-9.238.686-12.272.188 0 0 .62.513 3.806.715z",
"viewbox": "0 0 24 24",
"color": "#f97316",
"glow": "rgba(249,115,22,0.5)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"c": {
"path": "M16.5 9.5C16.5 7.01 14.49 5 12 5S7.5 7.01 7.5 9.5s2.01 4.5 4.5 4.5 4.5-2.01 4.5-4.5zM12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z",
"viewbox": "0 0 24 24",
"color": "#60a5fa",
"glow": "rgba(96,165,250,0.5)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"cpp": {
"path": "M16.5 9.5C16.5 7.01 14.49 5 12 5S7.5 7.01 7.5 9.5s2.01 4.5 4.5 4.5 4.5-2.01 4.5-4.5zM12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zM15 9h2v2h-2V9zm0 4h2v2h-2v-2z",
"viewbox": "0 0 24 24",
"color": "#60a5fa",
"glow": "rgba(96,165,250,0.5)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"h": {
"path": "M6 4h2v6h8V4h2v16h-2v-7H8v7H6V4z",
"viewbox": "0 0 24 24",
"color": "#94a3b8",
"glow": "rgba(148,163,184,0.4)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"cs": {
"path": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z M15 11h-2V9h-2v2H9v2h2v2h2v-2h2z",
"viewbox": "0 0 24 24",
"color": "#a855f7",
"glow": "rgba(168,85,247,0.5)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"go": {
"path": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z",
"viewbox": "0 0 24 24",
"color": "#06b6d4",
"glow": "rgba(6,182,212,0.5)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"rs": {
"path": "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z",
"viewbox": "0 0 24 24",
"color": "#fb923c",
"glow": "rgba(251,146,60,0.5)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"swift": {
"path": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm5 13l-4-3-4 3V7h8v8z",
"viewbox": "0 0 24 24",
"color": "#f97316",
"glow": "rgba(249,115,22,0.5)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"kt": {
"path": "M12 2l-5.5 9h11L12 2zm0 3.84L13.93 9h-3.87L12 5.84zM17.5 13c-2.49 0-4.5 2.01-4.5 4.5s2.01 4.5 4.5 4.5 4.5-2.01 4.5-4.5-2.01-4.5-4.5-4.5zm0 7c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z",
"viewbox": "0 0 24 24",
"color": "#a855f7",
"glow": "rgba(168,85,247,0.5)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"rb": {
"path": "M12 2l2 7h7l-5.5 4 2 7L12 16.5 6.5 20l2-7L3 9h7l2-7z",
"viewbox": "0 0 24 24",
"color": "#ef4444",
"glow": "rgba(239,68,68,0.5)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"pl": {
"path": "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z",
"viewbox": "0 0 24 24",
"color": "#94a3b8",
"glow": "rgba(148,163,184,0.4)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"json": {
"path": "M5 3h2v18H5zm7 0h2v18h-2zm7 0h2v18h-2z M4 8h16v2H4zm0 6h16v2H4z",
"viewbox": "0 0 24 24",
"color": "#94a3b8",
"glow": "rgba(148,163,184,0.4)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"xml": {
"path": "M5 3h2v18H5zm7 0h2v18h-2zm7 0h2v18h-2z M4 8h16v2H4zm0 6h16v2H4z",
"viewbox": "0 0 24 24",
"color": "#94a3b8",
"glow": "rgba(148,163,184,0.4)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"yaml": {
"path": "M5 3h2v18H5zm7 0h2v18h-2zm7 0h2v18h-2z M4 8h16v2H4zm0 6h16v2H4z",
"viewbox": "0 0 24 24",
"color": "#94a3b8",
"glow": "rgba(148,163,184,0.4)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"yml": {
"path": "M5 3h2v18H5zm7 0h2v18h-2zm7 0h2v18h-2z M4 8h16v2H4zm0 6h16v2H4z",
"viewbox": "0 0 24 24",
"color": "#94a3b8",
"glow": "rgba(148,163,184,0.4)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"toml": {
"path": "M5 3h2v18H5zm7 0h2v18h-2zm7 0h2v18h-2z M4 8h16v2H4zm0 6h16v2H4z",
"viewbox": "0 0 24 24",
"color": "#94a3b8",
"glow": "rgba(148,163,184,0.4)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"ini": {
"path": "M5 3h2v18H5zm7 0h2v18h-2zm7 0h2v18h-2z M4 8h16v2H4zm0 6h16v2H4z",
"viewbox": "0 0 24 24",
"color": "#94a3b8",
"glow": "rgba(148,163,184,0.4)",
"bg_color": "rgba(148,163,184,0.08)",
"category": "code"
},
"__default__": {
"path": "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M16 13H8",
"viewbox": "0 0 24 24",
"color": "#f3e6e4",
"glow": "rgba(243,230,228,0.4)",
"bg_color": "rgba(200,30,44,0.10)",
"category": "default"
}
};
  window.vaultFileIcon = function (filename) {
    const parts = String(filename || '').split('.');
    const ext = parts.length > 1 ? parts.pop().toLowerCase() : '';
    return Object.assign({ ext: ext }, ICONS[ext] || ICONS['__default__']);
  };
  window.vaultIconElement = function (filename) {
    const ic = window.vaultFileIcon(filename);
    const box = document.createElement('div');
    box.className = 'file-icon';
    box.style.setProperty('--icon-color', ic.color);
    box.style.setProperty('--icon-glow', ic.glow);
    box.style.setProperty('--icon-bg', ic.bg_color);
    const NS = 'http://www.w3.org/2000/svg';
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('viewBox', ic.viewbox);
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '1.8');
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');
    svg.setAttribute('width', '20');
    svg.setAttribute('height', '20');
    const p = document.createElementNS(NS, 'path');
    p.setAttribute('d', ic.path);
    svg.appendChild(p);
    box.appendChild(svg);
    return box;
  };
})();
