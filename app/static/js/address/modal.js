/**
 * static/js/address/modal.js
 * GUA.modal.open('add')
 * GUA.modal.open('edit', id, addrObj)
 * GUA.modal.close()
 *
 * GUA.confirmDelete(id, name)  — custom confirm dialog
 * GUA.deleteDialog.confirm()
 * GUA.deleteDialog.cancel()
 */
(function () {
  'use strict';

  window.GUA = window.GUA || {};

  // ── Elements ─────────────────────────────────────────

  var _modalEl    = document.getElementById('addr-modal');
  var _panelEl    = document.getElementById('modal-panel');
  var _backdropEl = document.getElementById('modal-backdrop');
  var _formEl     = document.getElementById('addr-form');
  var _titleEl    = document.getElementById('modal-title');
  var _btnText    = document.getElementById('btn-text');
  var _btnSubmit  = document.getElementById('btn-submit');
  var _btnSpin    = document.getElementById('btn-spin');

  var _delDialog  = document.getElementById('delete-dialog');
  var _delPanel   = document.getElementById('del-panel');
  var _delBack    = document.getElementById('del-backdrop');
  var _delName    = document.getElementById('del-name');
  var _delForm    = document.getElementById('delete-form');

  // ── State ─────────────────────────────────────────────

  var _lastFocus = null;
  // FIX: Track mode explicitly instead of reading DOM text (was buggy on close reset)
  var _currentMode = 'add';

  // ── Focus trap ────────────────────────────────────────

  var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function trapFocus(el) {
    var nodes = el.querySelectorAll(FOCUSABLE);
    if (!nodes.length) return;
    var first = nodes[0];
    var last  = nodes[nodes.length - 1];
    el._trap = function (e) {
      if (e.key !== 'Tab') return;
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
      }
    };
    el.addEventListener('keydown', el._trap);
    setTimeout(function () { first.focus(); }, 50);
  }

  function releaseFocus(el) {
    if (el._trap) { el.removeEventListener('keydown', el._trap); delete el._trap; }
  }

  // ── Modal ─────────────────────────────────────────────

  GUA.modal = {
    open: function (mode, id, addr) {
      _lastFocus   = document.activeElement;
      _currentMode = mode;
      var isEdit   = mode === 'edit' && id;

      // Build form action — FIX: preserve `next` query param correctly
      var nextParam = new URLSearchParams(window.location.search).get('next');
      var base = isEdit
        ? ('/profile/addresses/edit/' + id)
        : '/profile/addresses';
      _formEl.action = nextParam
        ? base + '?next=' + encodeURIComponent(nextParam)
        : base;

      // Labels
      _titleEl.textContent = isEdit ? 'Chỉnh sửa địa chỉ' : 'Thêm địa chỉ mới';
      _btnText.textContent = isEdit ? 'Cập nhật'           : 'Lưu địa chỉ';

      // Populate or reset
      if (isEdit && addr) {
        document.getElementById('addr-id').value       = id;
        document.getElementById('inp-name').value      = addr.full_name    || '';
        document.getElementById('inp-phone').value     = addr.phone        || '';
        document.getElementById('inp-addr').value      = addr.address_line || '';
        document.getElementById('inp-note').value      = addr.note         || '';
        // FIX: is_default from Supabase can be Python True (truthy) — coerce correctly
        document.getElementById('chk-default').checked = !!(addr.is_default);
        GUA.geo.preselectEdit(addr);
      } else {
        _formEl.reset();
        document.getElementById('addr-id').value = '';
        GUA.geo.reset();
      }

      // Reset submit button state
      _btnSubmit.disabled     = false;
      _btnText.textContent    = isEdit ? 'Cập nhật' : 'Lưu địa chỉ';
      _btnSpin.classList.add('hidden');

      // Show
      _modalEl.style.display = '';
      _modalEl.classList.add('is-open');
      _modalEl.removeAttribute('aria-hidden');
      document.body.style.overflow = 'hidden';
      trapFocus(_panelEl);
    },

    close: function () {
      releaseFocus(_panelEl);
      _panelEl.style.opacity    = '0';
      _panelEl.style.transform  = 'translateY(2rem)';
      _backdropEl.style.opacity = '0';

      setTimeout(function () {
        _modalEl.classList.remove('is-open');
        _modalEl.setAttribute('aria-hidden', 'true');
        _modalEl.style.display = 'none';
        // Reset panel inline styles (animation cleanup)
        _panelEl.style.cssText    = '';
        _backdropEl.style.cssText = '';
        document.body.style.overflow = '';
        // FIX: Reset button using tracked mode, not DOM text
        _btnSubmit.disabled  = false;
        _btnText.textContent = _currentMode === 'edit' ? 'Cập nhật' : 'Lưu địa chỉ';
        _btnSpin.classList.add('hidden');
        if (_lastFocus) _lastFocus.focus();
      }, 300);
    }
  };

  // ── Form submit — loading state ───────────────────────

  _formEl.addEventListener('submit', function (e) {
    // Sync hidden geo fields (safety guard)
    var selProv = document.getElementById('sel-prov');
    var selDist = document.getElementById('sel-dist');
    var selWard = document.getElementById('sel-ward');
    if (selProv.selectedIndex > 0) document.getElementById('hid-prov').value = selProv.options[selProv.selectedIndex].text;
    if (selDist.selectedIndex > 0) document.getElementById('hid-dist').value = selDist.options[selDist.selectedIndex].text;
    if (selWard.selectedIndex > 0) document.getElementById('hid-ward').value = selWard.options[selWard.selectedIndex].text;

    // HTML5 validation
    if (!this.checkValidity()) {
      e.preventDefault();
      this.reportValidity();
      return;
    }

    // Location completeness check
    if (!selProv.value || !selDist.value || !selWard.value) {
      e.preventDefault();
      GUA.toast('Vui lòng chọn đầy đủ Tỉnh → Quận → Phường', 'error');
      return;
    }

    // Activate loading state
    _btnSubmit.disabled  = true;
    _btnText.textContent = 'Đang lưu…';
    _btnSpin.classList.remove('hidden');
  });

  // ── Delete confirm dialog ─────────────────────────────

  var _pendingDeleteId = null;

  GUA.confirmDelete = function (id, name) {
    _pendingDeleteId  = id;
    _delName.textContent = name;

    _delDialog.style.display = '';
    _delDialog.classList.add('is-open');
    _delDialog.removeAttribute('aria-hidden');
    document.body.style.overflow = 'hidden';

    // Focus the cancel button (safer default)
    setTimeout(function () {
      var cancelBtn = _delDialog.querySelector('button');
      if (cancelBtn) cancelBtn.focus();
    }, 50);
  };

  GUA.deleteDialog = {
    confirm: function () {
      if (!_pendingDeleteId) return;
      _delForm.action = '/profile/addresses/delete/' + _pendingDeleteId;
      _delForm.submit();
    },
    cancel: function () {
      _pendingDeleteId = null;
      _delDialog.classList.remove('is-open');
      _delDialog.setAttribute('aria-hidden', 'true');
      setTimeout(function () {
        _delDialog.style.display = 'none';
        _delPanel.style.cssText  = '';
        _delBack.style.cssText   = '';
        document.body.style.overflow = '';
      }, 200);
    }
  };

  // ── Keyboard handlers ─────────────────────────────────

  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    if (_modalEl.classList.contains('is-open'))   GUA.modal.close();
    if (_delDialog.classList.contains('is-open')) GUA.deleteDialog.cancel();
  });

})();