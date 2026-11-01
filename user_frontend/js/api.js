/**
 * PrintX Customer Frontend Centralized API Client
 * Centralizes all customer-to-Django-backend communication.
 * Connects directly to the Django REST Multi-Shop Backend on port 8000.
 */

const Api = (function() {
  async function request(endpoint, options = {}) {
    const url = `${CONFIG.API_BASE_URL}${endpoint}`;
    const headers = options.headers ? { ...options.headers } : {};

    // For multipart/form-data (FormData), never set Content-Type header manually.
    // The browser automatically sets multipart/form-data with the correct boundary parameter.
    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    } else {
      delete headers['Content-Type'];
    }

    const config = {
      ...options,
      headers
    };

    try {
      const response = await fetch(url, config);

      let result;
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        result = await response.json();
      } else {
        const text = await response.text();
        result = { success: response.ok, message: text };
      }

      if (!response.ok) {
        let msg = (result && (result.message || result.detail || result.error));
        if (!msg && result && typeof result === 'object') {
          // If serializer validation errors returned (e.g. { field: ['error'] })
          const keys = Object.keys(result);
          if (keys.length > 0) {
            const first = result[keys[0]];
            msg = Array.isArray(first) ? `${keys[0]}: ${first[0]}` : `${keys[0]}: ${first}`;
          }
        }
        const err = new Error(msg || `Request failed with status ${response.status}`);
        err.status = response.status;
        err.data = result;
        throw err;
      }

      return result;
    } catch (error) {
      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        const networkErr = new Error('Cannot connect to PrintX Django backend on port 8000. Please verify the backend server is running.');
        networkErr.isNetworkError = true;
        throw networkErr;
      }
      throw error;
    }
  }

  return {
    get: (endpoint) => request(endpoint, { method: 'GET' }),
    post: (endpoint, data) => request(endpoint, { method: 'POST', body: JSON.stringify(data) }),

    uploadFile: (endpoint, file, extraFields = {}) => {
      const formData = new FormData();
      formData.append('file', file);
      for (const [key, value] of Object.entries(extraFields)) {
        if (value !== undefined && value !== null && value !== '') {
          formData.append(key, value);
        }
      }
      return request(endpoint, { method: 'POST', body: formData });
    },

    // 1. Documents
    documents: {
      upload: (file, shopPublicId) => {
        if (!shopPublicId) {
          throw new Error('A valid shop identifier is required to route your print upload.');
        }
        return Api.uploadFile('/documents/upload/', file, { shop_public_id: shopPublicId });
      },
      getById: (id) => Api.get(`/documents/${encodeURIComponent(id)}/`)
    },

    // 2. Shops
    shops: {
      list: () => Api.get('/shops/'),
      getPublic: (publicId) => Api.get(`/shops/public/${encodeURIComponent(publicId)}/`),
      getById: (id) => Api.get(`/shops/public/${encodeURIComponent(id)}/`)
    },

    // 3. Pricing & Authoritative Quotation
    pricing: {
      calculate: (payload) => Api.post('/pricing/calculate/', payload)
    },

    // 4. Orders
    orders: {
      create: (orderPayload) => Api.post('/orders/create/', orderPayload),
      track: (orderIdentifier, token = '') => {
        const query = token ? `?token=${encodeURIComponent(token)}` : '';
        return Api.get(`/orders/track/${encodeURIComponent(orderIdentifier)}/${query}`);
      },
      getById: (orderIdentifier, token = '') => {
        const query = token ? `?token=${encodeURIComponent(token)}` : '';
        return Api.get(`/orders/track/${encodeURIComponent(orderIdentifier)}/${query}`);
      }
    }
  };
})();
