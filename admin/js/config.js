/**
 * PrintX Admin Configuration
 * Centralized settings and backend endpoint URLs (auto-detects Localhost vs Production).
 */
const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

const CONFIG = {
  APP_NAME: 'PrintX Admin Hub',
  API_BASE_URL: isLocal 
    ? 'http://localhost:8000/api/v1' 
    : (localStorage.getItem('printx_api_url') || 'https://printx-backend.onrender.com/api/v1'),
  STORAGE_KEYS: {
    ADMIN_TOKEN: 'printx_admin_token',
    ADMIN_USER: 'printx_admin_user',
    ADMIN_SHOP: 'printx_admin_shop'
  },
  DEFAULT_CURRENCY: 'PKR',
  escapeHTML: function(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }
};

const escapeHTML = CONFIG.escapeHTML;

Object.freeze(CONFIG);
Object.freeze(CONFIG.STORAGE_KEYS);
