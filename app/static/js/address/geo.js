/**
 * static/js/address/geo.js
 * Province / District / Ward cascading selects
 * Uses: https://provinces.open-api.vn/api/?depth=3
 */
(function () {
  'use strict';

  window.GUA = window.GUA || {};

  var _selProv = document.getElementById('sel-prov');
  var _selDist = document.getElementById('sel-dist');
  var _selWard = document.getElementById('sel-ward');
  var _hidProv = document.getElementById('hid-prov');
  var _hidDist = document.getElementById('hid-dist');
  var _hidWard = document.getElementById('hid-ward');

  var _geoData     = null;
  var _pendingEdit = null;   // Set by modal.js before geoData resolves

  // ── Helpers ──────────────────────────────────────────

  function _buildOpts(select, items, placeholder) {
    select.innerHTML = '<option value="" disabled selected>' + placeholder + '</option>';
    items.forEach(function (item) {
      var o = document.createElement('option');
      o.value = item.code;
      o.textContent = item.name;
      select.appendChild(o);
    });
  }

  function _resetSelects() {
    _selDist.innerHTML = '<option value="" disabled selected>Chọn Tỉnh trước</option>';
    _selDist.disabled  = true;
    _selWard.innerHTML = '<option value="" disabled selected>Chọn Quận trước</option>';
    _selWard.disabled  = true;
    _hidProv.value = _hidDist.value = _hidWard.value = '';
  }

  // ── Preselect for edit mode ──────────────────────────

  function _preselectEdit(addr) {
    if (!_geoData) return;

    var provName = addr.province || addr.province_name || '';
    var prov = _geoData.find(function (p) { return p.name === provName; });
    if (!prov) return;

    _selProv.value = prov.code;
    _hidProv.value = prov.name;
    _buildOpts(_selDist, prov.districts, 'Chọn Quận/Huyện');
    _selDist.disabled = false;

    var distName = addr.district || addr.district_name || '';
    var dist = prov.districts.find(function (d) { return d.name === distName; });
    if (!dist) return;

    _selDist.value = dist.code;
    _hidDist.value = dist.name;
    _buildOpts(_selWard, dist.wards, 'Chọn Phường/Xã');
    _selWard.disabled = false;

    var wardName = addr.ward || addr.ward_name || '';
    var ward = dist.wards.find(function (w) { return w.name === wardName; });
    if (ward) {
      _selWard.value = ward.code;
      _hidWard.value = ward.name;
    }
  }

  // ── Load geo data ────────────────────────────────────

  function _loadGeoData() {
    if (_geoData) return;
    _selProv.disabled = true;
    _selProv.innerHTML = '<option value="" disabled selected>Đang tải…</option>';

    fetch('https://provinces.open-api.vn/api/?depth=3')
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (data) {
        _geoData = data;
        _buildOpts(_selProv, data, 'Chọn Tỉnh/Thành phố');
        _selProv.disabled = false;
        // If modal opened before data loaded, preselect now
        if (_pendingEdit) {
          _preselectEdit(_pendingEdit);
          _pendingEdit = null;
        }
      })
      .catch(function (err) {
        console.error('[GUA] Province API error:', err);
        _selProv.innerHTML = '<option value="" disabled selected>Không tải được — thử lại</option>';
        _selProv.disabled = false;
      });
  }

  // ── Select event listeners ────────────────────────────

  _selProv.addEventListener('change', function () {
    if (!_geoData) return;
    _hidProv.value = this.options[this.selectedIndex].text;
    _hidDist.value = '';
    _hidWard.value = '';
    _selDist.innerHTML = '<option value="" disabled selected>Chọn Quận/Huyện</option>';
    _selDist.disabled  = true;
    _selWard.innerHTML = '<option value="" disabled selected>Chọn Phường/Xã</option>';
    _selWard.disabled  = true;

    var provCode = parseInt(this.value);
    var prov = _geoData.find(function (p) { return p.code === provCode; });
    if (prov && prov.districts.length) {
      _buildOpts(_selDist, prov.districts, 'Chọn Quận/Huyện');
      _selDist.disabled = false;
    }
  });

  _selDist.addEventListener('change', function () {
    if (!_geoData) return;
    _hidDist.value = this.options[this.selectedIndex].text;
    _hidWard.value = '';
    _selWard.innerHTML = '<option value="" disabled selected>Chọn Phường/Xã</option>';
    _selWard.disabled  = true;

    var provCode = parseInt(_selProv.value);
    var distCode = parseInt(this.value);
    var prov = _geoData.find(function (p) { return p.code === provCode; });
    var dist = prov && prov.districts.find(function (d) { return d.code === distCode; });
    if (dist && dist.wards.length) {
      _buildOpts(_selWard, dist.wards, 'Chọn Phường/Xã');
      _selWard.disabled = false;
    }
  });

  _selWard.addEventListener('change', function () {
    _hidWard.value = this.options[this.selectedIndex].text;
  });

  // ── Public API ────────────────────────────────────────

  GUA.geo = {
    load: _loadGeoData,
    reset: _resetSelects,
    preselectEdit: function (addr) {
      if (_geoData) {
        _preselectEdit(addr);
      } else {
        _pendingEdit = addr;  // Will preselect once data loads
      }
    }
  };

  // Preload immediately on page load — don't wait for modal
  _loadGeoData();

})();