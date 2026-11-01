/**
 * PrintX Customer Order Tracking Logic
 * Queries live status from the Django backend.
 */

document.addEventListener('DOMContentLoaded', () => {
  App.initNavbar('order-tracking');

  const urlParams = new URLSearchParams(window.location.search);
  const orderIdParam = urlParams.get('orderId') || urlParams.get('order');
  let tokenParam = urlParams.get('token') || '';

  const searchInput = document.getElementById('tracking-search-input');
  const searchBtn = document.getElementById('tracking-search-btn');
  const trackingResultCard = document.getElementById('tracking-result-card');
  const refreshBtn = document.getElementById('refresh-order-btn');
  const cancelBtn = document.getElementById('cancel-order-btn');
  const alertContainerId = 'tracking-alert-container';


  const orderNumberEl = document.getElementById('track-order-number');
  const orderStatusBadgeEl = document.getElementById('track-status-badge');
  const orderDocNameEl = document.getElementById('track-doc-name');
  const orderShopNameEl = document.getElementById('track-shop-name');
  const orderCopiesEl = document.getElementById('track-copies');
  const orderTotalEl = document.getElementById('track-total');
  const orderDateEl = document.getElementById('track-date');
  const orderPaymentStatusEl = document.getElementById('track-payment-status');
  const orderInstructionsEl = document.getElementById('track-instructions');

  let currentLoadedOrder = null;

  const STATUS_STEP_INDEX = {
    'pending': 1,
    'confirmed': 2,
    'printing': 3,
    'ready_for_pickup': 4,
    'completed': 5,
    'blocked': -1
  };

  if (orderIdParam) {
    if (searchInput) searchInput.value = orderIdParam;
    fetchOrderDetails(orderIdParam);
  }

  if (searchBtn && searchInput) {
    searchBtn.addEventListener('click', () => {
      const id = searchInput.value.trim();
      if (!id) {
        App.showAlert(alertContainerId, 'Please enter an Order Number.');
        return;
      }
      fetchOrderDetails(id);
    });
  }

  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      if (currentLoadedOrder) fetchOrderDetails(currentLoadedOrder.order_number);
    });
  }

  async function fetchOrderDetails(orderIdentifier) {
    App.clearAlert(alertContainerId);
    if (searchBtn) App.setButtonLoading(searchBtn, true, 'Searching...');

    // If token wasn't in URL query, check if cached receipt matches this order
    if (!tokenParam) {
      const cached = localStorage.getItem('printx_last_receipt');
      if (cached) {
        try {
          const parsed = JSON.parse(cached);
          if (parsed.order_number === orderIdentifier || parsed.id == orderIdentifier) {
            tokenParam = parsed.access_token || '';
          }
        } catch(e) {}
      }
    }

    try {
      const res = await Api.orders.track(orderIdentifier, tokenParam);
      if (res && res.success && res.data) {
        renderOrder(res.data);
      } else {
        throw new Error('Order not found.');
      }
    } catch (err) {
      // Fallback to cached receipt if offline
      const cached = localStorage.getItem('printx_last_receipt');
      if (cached) {
        const parsed = JSON.parse(cached);
        if (parsed.order_number === orderIdentifier || parsed.id === orderIdentifier) {
          renderOrder(parsed);
          return;
        }
      }
      if (trackingResultCard) trackingResultCard.classList.add('d-none');
      App.showAlert(alertContainerId, err.message || 'Unable to retrieve order details from backend.');
    } finally {
      if (searchBtn) App.setButtonLoading(searchBtn, false);
    }
  }


  function renderOrder(order) {
    currentLoadedOrder = order;

    if (orderNumberEl) orderNumberEl.textContent = order.order_number;
    if (orderDocNameEl) orderDocNameEl.textContent = order.document_name;
    if (orderShopNameEl) orderShopNameEl.textContent = order.shop_name;
    if (orderCopiesEl) orderCopiesEl.textContent = `${order.copies} copy(s), ${order.color_mode === 'color' ? 'Color' : 'B&W'}, ${order.paper_size}`;
    if (orderTotalEl) orderTotalEl.textContent = App.formatCurrency(order.total_price, order.currency);
    if (orderDateEl) orderDateEl.textContent = App.formatDate(order.created_at);
    if (orderPaymentStatusEl) orderPaymentStatusEl.textContent = `${order.payment_method.replace(/_/g, ' ')} (${order.payment_status.toUpperCase()})`;
    if (orderInstructionsEl) orderInstructionsEl.textContent = order.special_instructions || 'None';

    if (orderStatusBadgeEl) {
      orderStatusBadgeEl.className = `badge badge-${order.status}`;
      orderStatusBadgeEl.textContent = order.status.replace(/_/g, ' ').toUpperCase();
    }

    updateStatusSteps(order.status);

    if (trackingResultCard) {
      trackingResultCard.classList.remove('d-none');
      trackingResultCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }

  function updateStatusSteps(status) {
    const stepIndex = STATUS_STEP_INDEX[status] || 1;
    const isBlocked = status === 'blocked';

    const steps = [
      document.getElementById('step-1'),
      document.getElementById('step-2'),
      document.getElementById('step-3'),
      document.getElementById('step-4'),
      document.getElementById('step-5')
    ];

    steps.forEach((stepEl, idx) => {
      if (!stepEl) return;
      const stepNum = idx + 1;
      stepEl.classList.remove('active', 'completed');

      if (isBlocked) {
        if (stepNum === 1) stepEl.classList.add('completed');
      } else {
        if (stepNum < stepIndex) {
          stepEl.classList.add('completed');
        } else if (stepNum === stepIndex) {
          stepEl.classList.add('active');
        }
      }
    });

    const cancelledBanner = document.getElementById('cancelled-banner');
    if (cancelledBanner) {
      if (isBlocked) {
        cancelledBanner.classList.remove('d-none');
      } else {
        cancelledBanner.classList.add('d-none');
      }
    }
  }
});
