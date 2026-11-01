/**
 * PrintX Global Application Utilities
 * Navigation bar state, alerts, formatting helpers, and SVG icons.
 * Kiosk / QR-Scan Mode: Zero login or registration barrier.
 */

const App = (function() {
  /**
   * Professional SVG Icons (Strictly NO Emojis)
   */
  const ICONS = {
    printer: `<svg class="icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 14h12v8H6z"/></svg>`,
    upload: `<svg class="icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/></svg>`,
    file: `<svg class="icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`,
    check: `<svg class="icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
    clock: `<svg class="icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
    alert: `<svg class="icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
    qr: `<svg class="icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>`,
    location: `<svg class="icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>`
  };

  /**
   * Escape HTML strings to prevent XSS
   */
  function escapeHTML(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /**
   * Format monetary amount in PKR (Rs.)
   */
  function formatCurrency(amount, currency = 'PKR') {
    const num = Number(amount) || 0;
    if (currency === 'PKR' || !currency) {
      return `Rs. ${num.toLocaleString('en-PK', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(num);
  }

  /**
   * Format ISO date string
   */
  function formatDate(isoString) {
    if (!isoString) return '-';
    try {
      const d = new Date(isoString);
      return d.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return isoString;
    }
  }

  /**
   * Format bytes to readable size (KB, MB)
   */
  function formatBytes(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  /**
   * Render alert banner into a target container
   */
  function showAlert(containerId, message, type = 'error') {
    const container = document.getElementById(containerId);
    if (!container) return;

    const iconType = type === 'success' ? ICONS.check : ICONS.alert;
    container.innerHTML = `
      <div class="alert alert-${type}">
        ${iconType}
        <div>${escapeHTML(message)}</div>
      </div>
    `;
    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  /**
   * Clear alert banner
   */
  function clearAlert(containerId) {
    const container = document.getElementById(containerId);
    if (container) {
      container.innerHTML = '';
    }
  }

  /**
   * Set button loading state
   */
  function setButtonLoading(button, isLoading, loadingText = 'Processing...') {
    if (!button) return;
    if (isLoading) {
      button.dataset.originalHtml = button.innerHTML;
      button.disabled = true;
      button.innerHTML = `<span class="spinner"></span> <span>${escapeHTML(loadingText)}</span>`;
    } else {
      button.disabled = false;
      if (button.dataset.originalHtml) {
        button.innerHTML = button.dataset.originalHtml;
      }
    }
  }

  /**
   * Get currently active shop ID (from QR query string or local storage)
   */
  function getActiveShop() {
    const urlParams = new URLSearchParams(window.location.search);
    const shopFromUrl = urlParams.get('shop') || urlParams.get('shopId');
    if (shopFromUrl) {
      localStorage.setItem(CONFIG.STORAGE_KEYS.CURRENT_SHOP, shopFromUrl);
      return shopFromUrl;
    }
    return localStorage.getItem(CONFIG.STORAGE_KEYS.CURRENT_SHOP) || '';
  }

  /**
   * Initialize dynamic navigation bar in Kiosk / QR Scan mode
   */
  function initNavbar(activePage = '') {
    // Detect QR shop parameter from URL
    const activeShopId = getActiveShop();
    const isPages = window.location.pathname.includes('/pages/');

    const authSlot = document.getElementById('navbar-auth-slot');
    if (authSlot) {
      authSlot.innerHTML = `
        <div class="user-badge" style="background-color: var(--primary-light); color: var(--primary-dark); border-color: var(--border-subtle); display: inline-flex; align-items: center; gap: 6px;">
          ${ICONS.location}
          <span id="nav-shop-name">Print Shop Counter</span>
        </div>
      `;
    }

    // Update active nav styling
    const links = document.querySelectorAll('.navbar-link');
    links.forEach(l => {
      if (l.dataset.page === activePage) {
        l.classList.add('active');
      }
    });

    // Attempt to load shop name from Django backend
    if (activeShopId) {
      Api.shops.getPublic(activeShopId).then(res => {
        if (res && res.data && res.data.name) {
          const el = document.getElementById('nav-shop-name');
          if (el) el.textContent = res.data.name;
        }
      }).catch(() => {
        const el = document.getElementById('nav-shop-name');
        if (el) el.textContent = CONFIG.DEFAULT_SHOP_NAME || 'PrintX Counter';
      });
    } else {
      const el = document.getElementById('nav-shop-name');
      if (el) el.textContent = CONFIG.DEFAULT_SHOP_NAME || 'PrintX Counter';
    }
  }

  return {
    ICONS,
    escapeHTML,
    formatCurrency,
    formatDate,
    formatBytes,
    showAlert,
    clearAlert,
    setButtonLoading,
    getActiveShop,
    initNavbar
  };
})();
