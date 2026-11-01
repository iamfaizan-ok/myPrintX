/**
 * PrintX Admin Configuration
 * Centralized settings and backend endpoint URLs.
 */
const CONFIG = {
  APP_NAME: 'PrintX Admin Hub',
  // Django REST API Base URL
  API_BASE_URL: 'http://localhost:8000/api/v1',
  STORAGE_KEYS: {
    ADMIN_TOKEN: 'printx_admin_token',
    ADMIN_USER: 'printx_admin_user',
    ADMIN_SHOP: 'printx_admin_shop'
  },
  DEFAULT_CURRENCY: 'USD'
};

Object.freeze(CONFIG);
Object.freeze(CONFIG.STORAGE_KEYS);
