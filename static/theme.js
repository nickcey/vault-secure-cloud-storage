// Vault — Theme Manager
// Anti-FOUC : applique le thème AVANT le rendu initial

(function() {
  var STORAGE_KEY = 'vault_theme';
  
  // Lecture immédiate et application sur <html> ET <body>
  var savedTheme = localStorage.getItem(STORAGE_KEY);
  if (savedTheme === 'light') {
    document.documentElement.classList.add('light');
    if (document.body) document.body.classList.add('light');
  }

  // Fonction de toggle (fonctionne sur n'importe quel bouton #theme-toggle, .theme-toggle ou [data-theme-toggle])
  function toggleTheme() {
    var html = document.documentElement;
    var body = document.body;
    var isLight = html.classList.toggle('light');
    body.classList.toggle('light', isLight);
    
    // Sauvegarde
    localStorage.setItem(STORAGE_KEY, isLight ? 'light' : 'dark');
    
    // Mise à jour icônes et aria
    updateUI(isLight);
  }

  function updateUI(isLight) {
    // Icônes
    document.querySelectorAll('.theme-icon').forEach(function(el) {
      el.textContent = isLight ? '🌙' : '☀️';
    });
    
    // Aria pour accessibilité
    document.querySelectorAll('[id*="theme-toggle"], .theme-toggle, [data-theme-toggle]').forEach(function(btn) {
      btn.setAttribute('aria-pressed', isLight ? 'true' : 'false');
      btn.setAttribute('aria-label', isLight ? 'Passer en mode sombre' : 'Passer en mode clair');
    });
  }

  // Délégation d'événements (fonctionne même si le bouton est injecté dynamiquement)
  document.addEventListener('click', function(e) {
    var target = e.target.closest('[id*="theme-toggle"], .theme-toggle, [data-theme-toggle]');
    if (target) {
      e.preventDefault();
      toggleTheme();
    }
  });

  // Initialisation UI au chargement
  document.addEventListener('DOMContentLoaded', function() {
    updateUI(document.documentElement.classList.contains('light'));
  });

  // Export global (pour compatibilité avec d'anciens onclick)
  window.toggleTheme = toggleTheme;
})();
