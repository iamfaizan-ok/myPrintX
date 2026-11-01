/**
 * PrintX Customer Frontend Configuration
 * Connects directly to the Django REST Multi-Shop Backend on port 8000.
 */
const CONFIG = {
  APP_NAME: 'PrintX',
  API_BASE_URL: 'http://localhost:8000/api/v1',
  STORAGE_KEYS: {
    CURRENT_UPLOAD: 'printx_current_doc',
    CURRENT_ORDER_DRAFT: 'printx_order_draft',
    CURRENT_SHOP: 'printx_current_shop'
  },
  DEFAULT_SHOP_NAME: 'PrintX Counter',
  DEFAULT_CURRENCY: 'USD'
};

Object.freeze(CONFIG);
Object.freeze(CONFIG.STORAGE_KEYS);
