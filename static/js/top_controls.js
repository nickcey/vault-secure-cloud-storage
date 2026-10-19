/* ═══════════════════════════════════════════════════════════
   TOP CONTROLS - JavaScript
   Theme Toggle + Language Dropdown
   Intégration avec theme.js (clé: vault_theme)
   ═══════════════════════════════════════════════════════════ */

(function() {
  'use strict';

  var STORAGE_KEY = 'vault_theme';

  // Theme Toggle (délègue à theme.js via window.toggleTheme)
  function initTheme() {
    var savedTheme = localStorage.getItem(STORAGE_KEY);
    var icon = document.getElementById('themeIcon');
    
    if (icon) {
      var isLight = savedTheme === 'light';
      icon.textContent = isLight ? '☀️' : '🌙';
    }
  }

  // Language dropdown
  function toggleLangMenu(event) {
    event.stopPropagation();
    var menu = document.getElementById('langMenu');
    if (menu) {
      menu.classList.toggle('open');
    }
  }

  function closeLangMenu() {
    var menu = document.getElementById('langMenu');
    if (menu) {
      menu.classList.remove('open');
    }
  }

  // Close lang menu when clicking outside
  document.addEventListener('click', function(e) {
    if (!e.target.closest('.lang-dropdown')) {
      closeLangMenu();
    }
  });

  // Initialize on page load
  document.addEventListener('DOMContentLoaded', function() {
    initTheme();

    // Attach click handler to theme toggle (utilise la fonction globale de theme.js)
    var themeToggle = document.querySelector('.theme-toggle');
    if (themeToggle && window.toggleTheme) {
      themeToggle.addEventListener('click', function(e) {
        e.preventDefault();
        window.toggleTheme();
        // Update icon immédiatement
        var icon = document.getElementById('themeIcon');
        if (icon) {
          var isLight = document.documentElement.classList.contains('light');
          icon.textContent = isLight ? '☀️' : '🌙';
        }
      });
    }

    // Attach click handler to language button
    var langBtn = document.querySelector('.lang-btn');
    if (langBtn) {
      langBtn.addEventListener('click', toggleLangMenu);
    }
  });

  // Expose functions globally for inline onclick handlers (backward compatibility)
  window.toggleLangMenu = toggleLangMenu;
  window.closeLangMenu = closeLangMenu;
})();
