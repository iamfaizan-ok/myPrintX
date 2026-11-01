/**
 * PrintX Customer Frontend Configuration
 * Connects to Django Backend (auto-detects Localhost vs Production).
 */
const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

const CONFIG = {
  APP_NAME: 'PrintX',
  API_BASE_URL: isLocal 
    ? 'http://localhost:8000/api/v1' 
    : (localStorage.getItem('printx_api_url') || 'https://printx-backend.onrender.com/api/v1'),
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
