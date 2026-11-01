/**
 * PrintX Print Settings & Live Quotation Logic
 * Communicates with the Django Backend to calculate authoritative rates
 * and place shop-isolated print orders.
 */

document.addEventListener('DOMContentLoaded', async () => {
  App.initNavbar('print-settings');

  const urlParams = new URLSearchParams(window.location.search);
  const documentId = urlParams.get('documentId');
  const shopPublicId = urlParams.get('shop') || urlParams.get('shopId') || App.getActiveShop();
  const alertContainerId = 'print-alert-container';

  let cachedDoc = null;
  const cachedRaw = localStorage.getItem(CONFIG.STORAGE_KEYS.CURRENT_UPLOAD);
  if (cachedRaw) {
    try { cachedDoc = JSON.parse(cachedRaw); } catch(e) {}
  }

  if (!documentId && !cachedDoc) {
    App.showAlert(alertContainerId, 'No document found. Please upload a file first.');
    setTimeout(() => { window.location.href = 'upload.html'; }, 1800);
    return;
  }

  const docNameEl = document.getElementById('doc-name');
  const docPagesEl = document.getElementById('doc-pages');
  const docSizeEl = document.getElementById('doc-size');
  const shopSelect = document.getElementById('shop-select');
  const copiesInput = document.getElementById('copies-input');
  const pageRangeAllRadio = document.getElementById('page-range-all');
  const pageRangeCustomRadio = document.getElementById('page-range-custom');
  const pageRangeCustomInput = document.getElementById('page-range-custom-input');
  const duplexCheckbox = document.getElementById('duplex-checkbox');
  const specialInstructionsInput = document.getElementById('special-instructions');

  const pricePagesSubtotalEl = document.getElementById('price-pages-subtotal');
  const priceBindingFeeEl = document.getElementById('price-binding-fee');
  const priceTaxEl = document.getElementById('price-tax');
  const priceTotalEl = document.getElementById('price-total');
  const pricePageCountEl = document.getElementById('price-selected-pages');
  const placeOrderBtn = document.getElementById('place-order-btn');

  let currentDoc = cachedDoc || { id: documentId, originalName: 'Document.pdf', totalPages: 1, sizeBytes: 102400 };
  let calculationTimeout = null;
  let latestBreakdown = null;

  // Initialize: Load real document & shops from Django backend
  try {
    if (documentId) {
      try {
        const docRes = await Api.documents.getById(documentId);
        if (docRes && docRes.success && docRes.data) {
          currentDoc = docRes.data;
        }
      } catch (e) {}
    }

    docNameEl.textContent = currentDoc.original_name || currentDoc.originalName;
    docPagesEl.textContent = `${currentDoc.total_pages || currentDoc.totalPages} page(s)`;
    docSizeEl.textContent = App.formatBytes(currentDoc.size_bytes || currentDoc.sizeBytes);

    // Load available shops list
    try {
      const shopsRes = await Api.shops.list();
      if (shopsRes && shopsRes.success && Array.isArray(shopsRes.data) && shopsRes.data.length > 0) {
        shopSelect.innerHTML = '';
        shopsRes.data.forEach(s => {
          const opt = document.createElement('option');
          opt.value = s.public_id;
          opt.textContent = `${s.name} (${s.address})`;
          shopSelect.appendChild(opt);
        });

        if (shopPublicId) {
          shopSelect.value = shopPublicId;
        }
      }
    } catch (e) {}

    recalculatePrice();
  } catch (err) {
    App.showAlert(alertContainerId, err.message || 'Error initializing configuration.');
  }

  // Stepper buttons (+/-)
  const decBtn = document.getElementById('copies-decrement');
  const incBtn = document.getElementById('copies-increment');
  if (decBtn && copiesInput) {
    decBtn.addEventListener('click', () => {
      let val = parseInt(copiesInput.value, 10) || 1;
      if (val > 1) {
        copiesInput.value = val - 1;
        recalculatePrice();
      }
    });
  }
  if (incBtn && copiesInput) {
    incBtn.addEventListener('click', () => {
      let val = parseInt(copiesInput.value, 10) || 1;
      if (val < 500) {
        copiesInput.value = val + 1;
        recalculatePrice();
      }
    });
  }

  // Duplex radio selector
  document.querySelectorAll('input[name="duplexOption"]').forEach(r => {
    r.addEventListener('change', () => {
      if (duplexCheckbox) duplexCheckbox.checked = (r.value === 'double');
      recalculatePrice();
    });
  });

  // Range inputs
  if (pageRangeAllRadio && pageRangeCustomRadio && pageRangeCustomInput) {
    pageRangeAllRadio.addEventListener('change', () => {
      pageRangeCustomInput.disabled = true;
      recalculatePrice();
    });
    pageRangeCustomRadio.addEventListener('change', () => {
      pageRangeCustomInput.disabled = false;
      pageRangeCustomInput.focus();
      recalculatePrice();
    });
    pageRangeCustomInput.addEventListener('input', () => {
      clearTimeout(calculationTimeout);
      calculationTimeout = setTimeout(recalculatePrice, 300);
    });
  }

  [copiesInput, shopSelect].forEach(el => {
    if (el) el.addEventListener('change', recalculatePrice);
  });
  if (copiesInput) {
    copiesInput.addEventListener('input', () => {
      clearTimeout(calculationTimeout);
      calculationTimeout = setTimeout(recalculatePrice, 300);
    });
  }

  document.querySelectorAll('input[name="colorMode"], input[name="paperSize"], input[name="binding"]').forEach(r => {
    r.addEventListener('change', recalculatePrice);
  });

  const onlineNotice = document.getElementById('online-payment-notice');
  document.querySelectorAll('input[name="paymentOption"]').forEach(r => {
    r.addEventListener('change', () => {
      if (onlineNotice) {
        if (r.value === 'online') {
          onlineNotice.classList.remove('d-none');
        } else {
          onlineNotice.classList.add('d-none');
        }
      }
    });
  });

  function getPrintSettings() {
    const copies = parseInt(copiesInput.value, 10) || 1;
    let pageRange = 'all';
    if (pageRangeCustomRadio && pageRangeCustomRadio.checked) {
      pageRange = pageRangeCustomInput.value.trim() || 'all';
    }

    const colorModeEl = document.querySelector('input[name="colorMode"]:checked');
    const colorMode = colorModeEl ? colorModeEl.value : 'bw';

    const paperSizeEl = document.querySelector('input[name="paperSize"]:checked');
    const paperSize = paperSizeEl ? paperSizeEl.value : 'A4';

    const duplexEl = document.querySelector('input[name="duplexOption"]:checked');
    const duplex = duplexEl ? (duplexEl.value === 'double') : false;

    const bindingEl = document.querySelector('input[name="binding"]:checked');
    const binding = bindingEl ? bindingEl.value : 'none';

    return {
      document_id: currentDoc.id,
      copies,
      page_range: pageRange,
      color_mode: colorMode,
      paper_size: paperSize,
      duplex,
      binding
    };
  }

  async function recalculatePrice() {
    if (!currentDoc) return;
    App.clearAlert(alertContainerId);

    const payload = getPrintSettings();

    try {
      const res = await Api.pricing.calculate(payload);
      if (res && res.success && res.data) {
        latestBreakdown = res.data;
        pricePageCountEl.textContent = `${latestBreakdown.selectedPagesCount} of ${latestBreakdown.totalPagesInDoc} page(s)`;
        pricePagesSubtotalEl.textContent = App.formatCurrency(latestBreakdown.pagesSubtotal, latestBreakdown.currency);
        priceBindingFeeEl.textContent = App.formatCurrency(latestBreakdown.bindingFee, latestBreakdown.currency);
        priceTaxEl.textContent = App.formatCurrency(latestBreakdown.tax, latestBreakdown.currency);
        priceTotalEl.textContent = App.formatCurrency(latestBreakdown.totalPrice, latestBreakdown.currency);
        if (placeOrderBtn) placeOrderBtn.disabled = false;
      }
    } catch (err) {
      if (placeOrderBtn) placeOrderBtn.disabled = true;
      priceTotalEl.textContent = '--';
      App.showAlert(alertContainerId, err.message || 'Error calculating quotation.');
    }
  }

  let isSubmitting = false;

  if (placeOrderBtn) {
    placeOrderBtn.addEventListener('click', async () => {
      if (isSubmitting) return;

      const settings = getPrintSettings();
      const selectedShopId = shopSelect.value || shopPublicId;

      if (!selectedShopId) {
        App.showAlert(alertContainerId, 'Please select a print shop.');
        return;
      }

      if (!latestBreakdown) {
        App.showAlert(alertContainerId, 'Please check your print options.');
        return;
      }

      const paymentRadio = document.querySelector('input[name="paymentOption"]:checked');
      const isOnlinePayment = paymentRadio && paymentRadio.value === 'online';

      if (isOnlinePayment) {
        App.showAlert(alertContainerId, 'Online payment gateway integration is currently pending. Please select "Cash on Shop" to confirm your order and print immediately.');
        return;
      }

      isSubmitting = true;
      App.setButtonLoading(placeOrderBtn, true, 'Submitting to Shop Queue...');
      App.clearAlert(alertContainerId);

      const orderPayload = {
        shop_public_id: selectedShopId,
        document_id: currentDoc.id,
        copies: settings.copies,
        page_range: settings.page_range,
        color_mode: settings.color_mode,
        paper_size: settings.paper_size,
        duplex: settings.duplex,
        binding: settings.binding,
        payment_method: 'cash_on_pickup',
        special_instructions: specialInstructionsInput ? specialInstructionsInput.value.trim() : ''
      };

      try {
        const res = await Api.orders.create(orderPayload);
        if (res && res.success && res.data) {
          const order = res.data;
          localStorage.setItem('printx_last_receipt', JSON.stringify(order));
          localStorage.removeItem(CONFIG.STORAGE_KEYS.CURRENT_UPLOAD);
          const trackingToken = order.access_token ? `&token=${encodeURIComponent(order.access_token)}` : '';
          const shopParam = `&shop=${encodeURIComponent(order.shop_public_id || selectedShopId)}`;
          window.location.href = `order-confirmation.html?orderId=${encodeURIComponent(order.order_number)}${trackingToken}${shopParam}`;
        } else {
          throw new Error((res && res.message) || 'Failed to place print order.');
        }
      } catch (err) {
        isSubmitting = false;
        App.showAlert(alertContainerId, err.message || 'Error placing order.');
        App.setButtonLoading(placeOrderBtn, false);
      }
    });
  }
});
