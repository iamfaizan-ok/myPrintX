/**
 * PrintX Admin Centralized API Client
 * Manages all communication with the Django REST Backend for Shop Admins.
 */

const AdminApi = (function() {
  async function request(endpoint, options = {}) {
    const url = `${CONFIG.API_BASE_URL}${endpoint}`;
    const headers = options.headers || {};

    const token = localStorage.getItem(CONFIG.STORAGE_KEYS.ADMIN_TOKEN);
    if (token) {
      headers['Authorization'] = `Token ${token}`;
    }

    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    const config = {
      ...options,
      headers
    };

    try {
      const response = await fetch(url, config);

      if (response.status === 401) {
        localStorage.removeItem(CONFIG.STORAGE_KEYS.ADMIN_TOKEN);
        localStorage.removeItem(CONFIG.STORAGE_KEYS.ADMIN_USER);
        localStorage.removeItem(CONFIG.STORAGE_KEYS.ADMIN_SHOP);
        
        const path = window.location.pathname;
        if (!path.includes('login.html') && !path.includes('signup.html')) {
          const isPages = path.includes('/pages/');
          window.location.href = isPages ? 'login.html' : 'pages/login.html';
        }
        throw new Error('Your session has expired. Please sign in again.');
      }

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

        // 1. Check for nested DRF 'errors' object
        if (!msg && result && result.errors) {
          if (typeof result.errors === 'string') {
            msg = result.errors;
          } else if (typeof result.errors === 'object') {
            const errKeys = Object.keys(result.errors);
            if (errKeys.length > 0) {
              const errVal = result.errors[errKeys[0]];
              msg = Array.isArray(errVal) ? errVal[0] : String(errVal);
            }
          }
        }

        // 2. Fallback: extract from other fields, skipping boolean 'success'
        if (!msg && result && typeof result === 'object') {
          const keys = Object.keys(result).filter(k => k !== 'success');
          if (keys.length > 0) {
            const first = result[keys[0]];
            msg = Array.isArray(first) ? first[0] : String(first);
          }
        }

        const err = new Error(msg || 'Invalid email address or password. Please verify your credentials.');
        err.status = response.status;
        err.data = result;
        throw err;
      }

      return result;
    } catch (error) {
      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        const networkErr = new Error('Cannot connect to PrintX Django backend on port 8000. Please ensure the server is active.');
        networkErr.isNetworkError = true;
        throw networkErr;
      }
      throw error;
    }
  }

  return {
    get: (endpoint) => request(endpoint, { method: 'GET' }),
    post: (endpoint, data) => request(endpoint, { method: 'POST', body: JSON.stringify(data) }),
    patch: (endpoint, data) => request(endpoint, { method: 'PATCH', body: JSON.stringify(data) }),

    auth: {
      signup: (data) => AdminApi.post('/admin/auth/signup/', data),
      login: (credentials) => AdminApi.post('/admin/auth/login/', credentials),
      getProfile: () => AdminApi.get('/admin/auth/me/'),
      updateProfile: (data) => AdminApi.patch('/admin/auth/me/', data),
      logout: () => AdminApi.post('/admin/auth/logout/', {})
    },

    dashboard: {
      getStats: () => AdminApi.get('/admin/dashboard/stats/')
    },

    orders: {
      list: (status = '', search = '', page = null, pageSize = 10) => {
        const params = new URLSearchParams();
        if (status) params.append('status', status);
        if (search) params.append('search', search);
        if (page) {
          params.append('page', page);
          params.append('page_size', pageSize);
        }
        const query = params.toString() ? `?${params.toString()}` : '';
        return AdminApi.get(`/admin/orders/${query}`);
      },
      getById: (id) => AdminApi.get(`/admin/orders/${encodeURIComponent(id)}/`),
      approvePayment: (id) => AdminApi.post(`/admin/orders/${encodeURIComponent(id)}/pay-ok/`, {}),
      authorizePrint: (id) => AdminApi.post(`/admin/orders/${encodeURIComponent(id)}/authorize-print/`, {}),
      block: (id, reason) => AdminApi.post(`/admin/orders/${encodeURIComponent(id)}/block/`, { reason })
    },

    qr: {
      getOrCreate: (data = {}) => AdminApi.post('/admin/qr/generate/', data),
      getDetails: (frontendUrl = '') => {
        const query = frontendUrl ? `?frontend_url=${encodeURIComponent(frontendUrl)}` : '';
        return AdminApi.get(`/admin/qr/details/${query}`);
      }
    },

    shop: {
      getProfile: () => AdminApi.get('/admin/shop/profile/'),
      updateProfile: (data) => AdminApi.patch('/admin/shop/profile/', data)
    },

    agent: {
      getToken: () => AdminApi.get('/admin/agent/token/'),
      regenerateToken: () => AdminApi.post('/admin/agent/token/', {})
    }
  };
})();

