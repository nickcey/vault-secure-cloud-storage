// Loader Utility Functions for Vault - Secure Cloud Storage

/**
 * Add loading state to a button
 * @param {HTMLButtonElement} btn - The button to add loader to
 * @param {string} originalText - The original button text (optional)
 */
function setButtonLoading(btn, originalText = null) {
  if (!btn) return;
  
  btn.classList.add('btn-loader');
  if (originalText) {
    btn.dataset.originalText = originalText;
  } else {
    btn.dataset.originalText = btn.textContent;
  }
  btn.disabled = true;
}

/**
 * Remove loading state from a button
 * @param {HTMLButtonElement} btn - The button to remove loader from
 */
function removeButtonLoading(btn) {
  if (!btn) return;
  
  btn.classList.remove('btn-loader');
  btn.disabled = false;
  if (btn.dataset.originalText) {
    btn.textContent = btn.dataset.originalText;
  }
}

/**
 * Show full page loader overlay
 * @param {string} text - Text to display (optional)
 */
function showPageLoader(text = 'Chargement...') {
  let overlay = document.querySelector('.page-loader-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.className = 'page-loader-overlay';
    overlay.innerHTML = `
      <div class="page-loader-spinner"></div>
      <div class="page-loader-text">${text}</div>
    `;
    document.body.appendChild(overlay);
  } else {
    overlay.querySelector('.page-loader-text').textContent = text;
    overlay.style.display = 'flex';
  }
}

/**
 * Hide full page loader overlay
 */
function hidePageLoader() {
  const overlay = document.querySelector('.page-loader-overlay');
  if (overlay) {
    overlay.style.display = 'none';
  }
}

/**
 * Setup form with loading state
 * @param {HTMLFormElement} form - The form to setup
 * @param {string} submitBtnSelector - Selector for the submit button
 */
function setupFormLoader(form, submitBtnSelector = 'button[type="submit"]') {
  if (!form) return;
  
  const submitBtn = form.querySelector(submitBtnSelector);
  if (!submitBtn) return;
  
  form.addEventListener('submit', function(e) {
    setButtonLoading(submitBtn);
  });
  
  // If form submission fails, remove loader
  form.addEventListener('submit-error', function() {
    removeButtonLoading(submitBtn);
  });
}
