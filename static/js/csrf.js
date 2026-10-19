/**
 * Protection CSRF pour les requêtes AJAX
 * Ajoute automatiquement le token CSRF dans les headers
 */

// Récupérer le token CSRF depuis une meta tag
function getCSRFToken() {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) {
        return metaTag.getAttribute('content');
    }
    
    // Fallback: chercher dans un input hidden
    const inputToken = document.querySelector('input[name="csrf_token"]');
    if (inputToken) {
        return inputToken.value;
    }
    
    return null;
}

// Ajouter le token CSRF aux requêtes fetch
const originalFetch = window.fetch;
window.fetch = function(url, options = {}) {
    // Ne modifier que les requêtes POST, PUT, PATCH, DELETE
    const method = (options.method || 'GET').toUpperCase();
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
        options.headers = options.headers || {};
        
        // Si le body est FormData, ajouter le token dedans
        if (options.body instanceof FormData) {
            const token = getCSRFToken();
            if (token && !options.body.has('csrf_token')) {
                options.body.append('csrf_token', token);
            }
            if (token) {
                if (options.headers instanceof Headers) {
                    if (!options.headers.has('X-CSRFToken')) {
                        options.headers.set('X-CSRFToken', token);
                    }
                } else if (!options.headers['X-CSRFToken'] && !options.headers['X-CSRF-Token']) {
                    options.headers['X-CSRFToken'] = token;
                }
            }
        } else {
            // Sinon, ajouter dans les headers
            if (!options.headers['X-CSRFToken']) {
                const token = getCSRFToken();
                if (token) {
                    options.headers['X-CSRFToken'] = token;
                }
            }
        }
    }
    
    return originalFetch(url, options);
};

// Ajouter le token CSRF aux requêtes XMLHttpRequest
(function() {
    const originalOpen = XMLHttpRequest.prototype.open;
    const originalSend = XMLHttpRequest.prototype.send;
    
    XMLHttpRequest.prototype.open = function(method, url) {
        this._method = method.toUpperCase();
        return originalOpen.apply(this, arguments);
    };
    
    XMLHttpRequest.prototype.send = function(body) {
        if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(this._method)) {
            const token = getCSRFToken();
            if (token) {
                this.setRequestHeader('X-CSRFToken', token);
            }
        }
        return originalSend.apply(this, arguments);
    };
})();

console.log('[CSRF] Protection CSRF active pour AJAX');
