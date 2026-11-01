/**
 * PrintX Admin Authentication & Session Guard
 */

const AdminAuth = (function() {
  function getToken() {
    return localStorage.getItem(CONFIG.STORAGE_KEYS.ADMIN_TOKEN);
  }

  function getAdmin() {
    const raw = localStorage.getItem(CONFIG.STORAGE_KEYS.ADMIN_USER);
    if (!raw) return null;
    try { return JSON.parse(raw); } catch (e) { return null; }
  }

  function getShop() {
    const raw = localStorage.getItem(CONFIG.STORAGE_KEYS.ADMIN_SHOP);
    if (!raw) return null;
    try { return JSON.parse(raw); } catch (e) { return null; }
  }

  function setSession(token, user, shop) {
    if (token) localStorage.setItem(CONFIG.STORAGE_KEYS.ADMIN_TOKEN, token);
    if (user) localStorage.setItem(CONFIG.STORAGE_KEYS.ADMIN_USER, JSON.stringify(user));
    if (shop) localStorage.setItem(CONFIG.STORAGE_KEYS.ADMIN_SHOP, JSON.stringify(shop));
  }

  function clearSession() {
    localStorage.removeItem(CONFIG.STORAGE_KEYS.ADMIN_TOKEN);
    localStorage.removeItem(CONFIG.STORAGE_KEYS.ADMIN_USER);
    localStorage.removeItem(CONFIG.STORAGE_KEYS.ADMIN_SHOP);
  }

  function isAuthenticated() {
    return Boolean(getToken());
  }

  function requireAdminAuth() {
    if (!isAuthenticated()) {
      window.location.href = '/admin/pages/login.html';
      return false;
    }
    return true;
  }

  async function logout() {
    try {
      await AdminApi.auth.logout();
    } catch (e) {
      // Clean local session even if network drops
    }
    clearSession();
    window.location.href = '/admin/pages/login.html';
  }

  function renderSidebar(activeMenu = 'dashboard') {
    const shop = getShop();
    const admin = getAdmin();
    const isPages = window.location.pathname.includes('/pages/');
    const basePath = isPages ? '' : 'pages/';
    const dashboardPath = isPages ? '../index.html' : 'index.html';

    const shopBadge = document.getElementById('topbar-shop-name');
    if (shopBadge && shop) {
      shopBadge.textContent = shop.name || 'My Print Shop';
    }

    const adminNameEl = document.getElementById('topbar-admin-name');
    if (adminNameEl && admin) {
      adminNameEl.textContent = admin.name || admin.email;
    }

    const logoutButtons = document.querySelectorAll('.action-logout');
    logoutButtons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        logout();
      });
    });
  }

  return {
    getToken,
    getAdmin,
    getShop,
    setSession,
    clearSession,
    isAuthenticated,
    requireAdminAuth,
    logout,
    renderSidebar
  };
})();
