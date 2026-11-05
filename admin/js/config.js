/**
 * PrintX Admin Configuration
 * Centralized settings and backend endpoint URLs (auto-detects Localhost vs LAN/Wi-Fi vs Production).
 */
const hostname = window.location.hostname;
const isLoopback = hostname === 'localhost' || hostname === '127.0.0.1';
const isLanIp = hostname.startsWith('192.168.') || 
                hostname.startsWith('10.') || 
                hostname.startsWith('172.') || 
                hostname.endsWith('.local');

let apiBaseUrl;
if (isLoopback) {
  apiBaseUrl = 'http://localhost:8000/api/v1';
} else if (isLanIp) {
  apiBaseUrl = `http://${hostname}:8000/api/v1`;
} else {
  apiBaseUrl = localStorage.getItem('printx_api_url') || 'https://printx-backend.onrender.com/api/v1';
}

const CONFIG = {
  APP_NAME: 'PrintX Admin Hub',
  API_BASE_URL: apiBaseUrl,
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
