// Vault Secure Cloud Storage - Dashboard JavaScript
console.log('[Dashboard] Script loaded');

// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', function() {
  console.log('[Dashboard] DOM loaded');
  
  // Initialize all event listeners
  initializeTheme();
  initializeLanguageMenu();
  initializeSearch();
  initializeModals();
  initializeDropdowns();
  
  console.log('[Dashboard] All initializations complete');
});

// Theme toggle
function toggleTheme(){
  document.body.classList.toggle('light');
  const icon = document.getElementById('themeIcon');
  if(icon){
    const isLight = document.body.classList.contains('light');
    icon.textContent = isLight ? '☀️' : '🌙';
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
  }
}

function initializeTheme(){
  const savedTheme = localStorage.getItem('theme');
  const themeIcon = document.getElementById('themeIcon');
  if(themeIcon){
    if(savedTheme === 'light'){
      document.body.classList.add('light');
      themeIcon.textContent = '☀️';
    } else {
      themeIcon.textContent = '🌙';
    }
  }
  console.log('[Theme] Initialized:', savedTheme || 'dark');
}

// Language dropdown
function toggleLangMenu(event){
  event.stopPropagation();
  const menu = document.getElementById('langMenu');
  if(menu) menu.classList.toggle('open');
}

function closeLangMenu(){
  const menu = document.getElementById('langMenu');
  if(menu) menu.classList.remove('open');
}

function initializeLanguageMenu(){
  document.addEventListener('click', function(e){
    if(!e.target.closest('.lang-dropdown')){
      closeLangMenu();
    }
  });
  console.log('[Language] Menu initialized');
}

// Search
function initializeSearch(){
  const searchEl = document.getElementById('fileSearch');
  if(searchEl){
    searchEl.addEventListener('input', function(e){
      const query = e.target.value.toLowerCase();
      const rows = document.querySelectorAll('.files-table tbody tr');
      rows.forEach(row => {
        const nameEl = row.querySelector('.file-name-text');
        if(nameEl){
          const name = nameEl.textContent.toLowerCase();
          row.style.display = name.includes(query) ? '' : 'none';
        }
      });
    });
    console.log('[Search] Initialized');
  }
}

// Rename Modal
let currentRenameId = null;

function showRename(fileId, fileName){
  console.log('[Rename] showRename called:', {fileId, fileName});
  currentRenameId = fileId;
  
  const input = document.getElementById('renameInput');
  const modal = document.getElementById('renameModal');
  
  console.log('[Rename] Elements:', {input, modal});
  
  if(input) input.value = fileName;
  if(modal){
    modal.classList.add('open');
    console.log('[Rename] Modal opened, classes:', modal.className);
  } else {
    console.error('[Rename] Modal not found!');
  }
}

function hideRename(){
  const modal = document.getElementById('renameModal');
  if(modal) modal.classList.remove('open');
  console.log('[Rename] Modal closed');
}

// Share Modal
let currentShareId = null;
const SUBMIT_LABEL_DEFAULT = 'Générer le lien';
const SUBMIT_LABEL_RESHOW = 'Voir le lien existant';

function showShare(fileId, fileName){
  console.log('[Share] showShare called:', {fileId, fileName});
  currentShareId = fileId;
  
  const fileNameEl = document.getElementById('shareFileName');
  const resultEl = document.getElementById('shareResult');
  const submitBtn = document.getElementById('shareSubmitBtn');
  const modal = document.getElementById('shareModal');
  
  if(fileNameEl) fileNameEl.textContent = fileName;
  if(resultEl) resultEl.style.display = 'none';
  if(submitBtn){
    submitBtn.disabled = false;
    submitBtn.textContent = SUBMIT_LABEL_DEFAULT;
  }
  if(modal){
    modal.classList.add('open');
    console.log('[Share] Modal opened');
    // Un lien actif existe-t-il déjà pour ce fichier ?
    fetch(`/share/create/${fileId}`, {
      method: 'POST',
      body: (() => { const fd = new FormData(); fd.append('password', ''); return fd; })()
    })
    .then(r => r.json().then(data => ({ ok: r.ok, status: r.status, data })))
    .then(({ ok, status, data }) => {
      if(ok && data.existing && data.url){
        if(submitBtn) submitBtn.textContent = SUBMIT_LABEL_RESHOW;
        showShareResult(data.url);
      }
    })
    .catch(() => { /* silencieux : l'utilisateur générera le lien normalement */ });
  } else {
    console.error('[Share] Modal not found!');
  }
}

function showShareResult(url){
  const urlEl = document.getElementById('shareUrl');
  const resultEl = document.getElementById('shareResult');
  if(urlEl) urlEl.textContent = url;
  if(resultEl) resultEl.style.display = 'block';
}

function hideShare(){
  const modal = document.getElementById('shareModal');
  if(modal) modal.classList.remove('open');
  console.log('[Share] Modal closed');
}

function doShare(){
  const password = document.getElementById('sharePassword').value;
  const expiry = document.getElementById('shareExpiry').value;
  const maxDl = document.getElementById('shareMaxDl').value;
  
  if(!password){
    alert("Mot de passe requis");
    return;
  }
  
  console.log('[Share] Generating link for file:', currentShareId);
  
  // Le backend attend du form-data (request.form), pas du JSON
  const formData = new FormData();
  formData.append('password', password);
  formData.append('expiry_hours', expiry);
  formData.append('max_downloads', maxDl);
  
  fetch(`/share/create/${currentShareId}`, {
    method: 'POST',
    body: formData
  })
  .then(r => r.json().then(data => ({ ok: r.ok, status: r.status, data })))
  .then(({ ok, status, data }) => {
    console.log('[Share] Response:', status, data);
    if(ok && data.url){
      showShareResult(data.url);
      const submitBtn = document.getElementById('shareSubmitBtn');
      if(submitBtn) submitBtn.textContent = data.existing ? SUBMIT_LABEL_RESHOW : SUBMIT_LABEL_DEFAULT;
    }else{
      alert(data.error || data.message || `Erreur ${status}`);
    }
  })
  .catch(err => {
    console.error('[Share] Error:', err);
    alert('Erreur réseau');
  });
}

function copyShareUrl(){
  const url = document.getElementById('shareUrl').textContent;
  navigator.clipboard.writeText(url).then(() => {
    alert("Lien copié");
  });
}

// Delete Modal
let currentDeleteId = null;

function confirmDelete(fileId){
  console.log('[Delete] confirmDelete called:', fileId);
  currentDeleteId = fileId;
  const modal = document.getElementById('deleteModal');
  if(modal){
    modal.classList.add('open');
    console.log('[Delete] Modal opened');
  }
}

function hideDelete(){
  const modal = document.getElementById('deleteModal');
  if(modal) modal.classList.remove('open');
  currentDeleteId = null;
  console.log('[Delete] Modal closed');
}

// Dropdown menus
function toggleMenu(event, menuId){
  event.stopPropagation();
  closeAllMenus();
  const menu = document.getElementById(menuId);
  if(menu){
    menu.classList.add('open');
    console.log('[Menu] Opened:', menuId);
  }
}

function closeAllMenus(){
  document.querySelectorAll('.dropdown-menu').forEach(menu => {
    menu.classList.remove('open');
  });
}

// User menu toggle
function toggleUserMenu(event){
  event.stopPropagation();
  const menu = event.currentTarget;
  const isActive = menu.classList.contains('active');
  
  document.querySelectorAll('.user-menu').forEach(m => {
    m.classList.remove('active');
  });
  
  if(!isActive){
    menu.classList.add('active');
  }
}

// Initialize all modals and event listeners
function getCSRFToken(){
  const metaTag = document.querySelector('meta[name="csrf-token"]');
  if(metaTag) return metaTag.getAttribute('content');
  const inputToken = document.querySelector('input[name="csrf_token"]');
  if(inputToken) return inputToken.value;
  return null;
}

function initializeModals(){
  // Rename form submit
  const renameForm = document.getElementById('renameForm');
  if(renameForm){
    renameForm.addEventListener('submit', function(e){
      console.log('[Rename] Form submit');
      e.preventDefault();
      const newName = document.getElementById('renameInput').value.trim();
      if(newName && currentRenameId){
        console.log('[Rename] Submitting rename for:', currentRenameId, newName);
        // POST avec token CSRF (la route /rename accepte POST)
        renameForm.action = `/rename/${currentRenameId}`;
        renameForm.method = 'POST';
        renameForm.submit();
      }
    });
    console.log('[Rename] Form listener attached');
  }
  
  // Delete confirm button
  const deleteBtn = document.getElementById('deleteConfirmBtn');
  if(deleteBtn){
    deleteBtn.addEventListener('click', function(){
      if(currentDeleteId){
        console.log('[Delete] Submitting delete for:', currentDeleteId);
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = `/delete/${currentDeleteId}`;
        // Token CSRF obligatoire (protection réactivée)
        const csrfToken = getCSRFToken();
        if(csrfToken){
          const input = document.createElement('input');
          input.type = 'hidden';
          input.name = 'csrf_token';
          input.value = csrfToken;
          form.appendChild(input);
        }
        document.body.appendChild(form);
        form.submit();
      }
    });
    console.log('[Delete] Button listener attached');
  }
  
  // Close modals on background click
  document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', function(e){
      if(e.target === modal){
        modal.classList.remove('open');
        console.log('[Modal] Closed via background click');
      }
    });
  });
  
  console.log('[Modals] All event listeners attached');
}

// Initialize dropdowns
function initializeDropdowns(){
  // Attach event listeners to rename buttons
  document.querySelectorAll('.rename-btn').forEach(btn => {
    btn.addEventListener('click', function(e){
      e.stopPropagation();
      const fileId = parseInt(this.getAttribute('data-file-id'));
      const fileName = this.getAttribute('data-file-name');
      console.log('[Rename] Button clicked:', {fileId, fileName});
      showRename(fileId, fileName);
      closeAllMenus();
    });
  });
  
  // Attach event listeners to share buttons
  document.querySelectorAll('.share-btn').forEach(btn => {
    btn.addEventListener('click', function(e){
      e.stopPropagation();
      const fileId = parseInt(this.getAttribute('data-file-id'));
      const fileName = this.getAttribute('data-file-name');
      console.log('[Share] Button clicked:', {fileId, fileName});
      showShare(fileId, fileName);
      closeAllMenus();
    });
  });
  
  // Close menus when clicking outside
  document.addEventListener('click', function(e){
    if(!e.target.closest('.menu-btn') && !e.target.closest('.dropdown-menu')){
      closeAllMenus();
    }
    
    // Close user menu when clicking outside
    if(!e.target.closest('.user-menu')){
      document.querySelectorAll('.user-menu').forEach(menu => {
        menu.classList.remove('active');
      });
    }
  });
  
  console.log('[Dropdowns] Click handlers attached');
}

console.log('[Dashboard] Script parsing complete');
