/**
 * PrintX Customer Document Upload Logic
 * Kiosk / QR-Scan Mode: Links directly with the scanned shop counter on the Django backend.
 * Enforces genuine PDF document upload and saves strictly to private storage.
 */

document.addEventListener('DOMContentLoaded', async () => {
  App.initNavbar('upload');

  const dropzone = document.getElementById('upload-dropzone');
  const fileInput = document.getElementById('file-input');
  const fileDetailsCard = document.getElementById('file-details-card');
  const fileNameEl = document.getElementById('file-name');
  const fileSizeEl = document.getElementById('file-size');
  const uploadBtn = document.getElementById('submit-upload-btn');
  const removeFileBtn = document.getElementById('remove-file-btn');
  const alertContainerId = 'upload-alert-container';
  const shopBannerText = document.getElementById('shop-banner-text');

  let selectedFile = null;
  const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50MB

  // 1. Resolve Active Shop from URL or Backend
  let activeShopId = App.getActiveShop();
  let activeShop = null;

  async function resolveShop() {
    try {
      if (activeShopId) {
        const res = await Api.shops.getPublic(activeShopId);
        if (res && res.success && res.data) {
          activeShop = res.data;
        }
      }

      // If no valid shop resolved yet, fetch available shops list from Django backend
      if (!activeShop) {
        const listRes = await Api.shops.list();
        if (listRes && listRes.success && Array.isArray(listRes.data) && listRes.data.length > 0) {
          activeShop = listRes.data[0];
          activeShopId = activeShop.public_id;
          localStorage.setItem(CONFIG.STORAGE_KEYS.CURRENT_SHOP, activeShopId);
        }
      }

      if (activeShop && shopBannerText) {
        shopBannerText.innerHTML = `
          <strong>Connected Counter:</strong> Uploading for <strong>${App.escapeHTML(activeShop.name)}</strong> (${App.escapeHTML(activeShop.address || 'Counter')}). No account required.
        `;
      } else if (shopBannerText) {
        shopBannerText.innerHTML = `
          <strong>Connected Counter:</strong> Please scan a shop counter QR code or select a shop counter.
        `;
      }
    } catch (e) {
      if (shopBannerText) {
        shopBannerText.innerHTML = `
          <strong>Shop Counter:</strong> Connecting to print counter.
        `;
      }
    }
  }

  await resolveShop();

  if (!dropzone || !fileInput) return;

  dropzone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    if (dt && dt.files && dt.files.length > 0) handleFileSelected(dt.files[0]);
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files && fileInput.files.length > 0) handleFileSelected(fileInput.files[0]);
  });

  if (removeFileBtn) {
    removeFileBtn.addEventListener('click', () => {
      selectedFile = null;
      fileInput.value = '';
      fileDetailsCard.classList.add('d-none');
      dropzone.classList.remove('d-none');
      uploadBtn.disabled = true;
      App.clearAlert(alertContainerId);
    });
  }

  function handleFileSelected(file) {
    App.clearAlert(alertContainerId);

    if (!file) return;

    if (file.size === 0) {
      App.showAlert(alertContainerId, 'The selected file is empty (0 bytes). Please select a valid document.');
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      App.showAlert(alertContainerId, `File too large (${App.formatBytes(file.size)}). Maximum allowed size is 50MB.`);
      return;
    }

    // Strict PDF validation check
    const isPdfExt = file.name && file.name.toLowerCase().endsWith('.pdf');
    const isPdfMime = file.type === 'application/pdf';

    if (!isPdfExt && !isPdfMime) {
      App.showAlert(alertContainerId, 'Invalid file format. Please select a genuine PDF document (.pdf).');
      return;
    }

    selectedFile = file;
    fileNameEl.textContent = file.name;
    fileSizeEl.textContent = App.formatBytes(file.size);

    dropzone.classList.add('d-none');
    fileDetailsCard.classList.remove('d-none');
    uploadBtn.disabled = false;
  }

  if (uploadBtn) {
    uploadBtn.addEventListener('click', async () => {
      if (!selectedFile) {
        App.showAlert(alertContainerId, 'Please select a PDF document first.');
        return;
      }

      if (!activeShopId) {
        App.showAlert(alertContainerId, 'Cannot determine target print shop. Please scan a shop QR code.');
        return;
      }

      App.clearAlert(alertContainerId);
      App.setButtonLoading(uploadBtn, true, 'Uploading to Shop Queue...');

      try {
        const response = await Api.documents.upload(selectedFile, activeShopId);
        if (response && response.success && response.data) {
          const docData = response.data;
          localStorage.setItem(CONFIG.STORAGE_KEYS.CURRENT_UPLOAD, JSON.stringify(docData));
          window.location.href = `print-settings.html?documentId=${encodeURIComponent(docData.id)}&shop=${encodeURIComponent(activeShopId)}`;
        } else {
          throw new Error((response && response.message) || 'Upload failed.');
        }
      } catch (err) {
        let msg = err.message || 'Error uploading file.';
        if (err.data && err.data.errors) {
          const errs = err.data.errors;
          const k = Object.keys(errs);
          if (k.length > 0) {
            msg = Array.isArray(errs[k[0]]) ? errs[k[0]][0] : errs[k[0]];
          }
        }
        App.showAlert(alertContainerId, msg);
        App.setButtonLoading(uploadBtn, false);
      }
    });
  }
});
