/**
 * PrintX Customer Frontend Configuration
 * Connects to Django Backend (auto-detects Localhost vs LAN/Wi-Fi vs Production).
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
  // Mobile device connecting to host machine via Wi-Fi / Local Area Network
  apiBaseUrl = `http://${hostname}:8000/api/v1`;
} else {
  apiBaseUrl = localStorage.getItem('printx_api_url') || 'https://printx-backend.onrender.com/api/v1';
}

const CONFIG = {
  APP_NAME: 'PrintX',
  API_BASE_URL: apiBaseUrl,
  STORAGE_KEYS: {
    CURRENT_UPLOAD: 'printx_current_doc',
    CURRENT_ORDER_DRAFT: 'printx_order_draft',
    CURRENT_SHOP: 'printx_current_shop'
  },
  DEFAULT_SHOP_NAME: 'PrintX Counter',
  DEFAULT_CURRENCY: 'PKR'
};

Object.freeze(CONFIG);
Object.freeze(CONFIG.STORAGE_KEYS);
