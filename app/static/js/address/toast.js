/**
 * static/js/address/toast.js
 * GUA.toast(msg, type?, duration?)
 * type: 'success' | 'error' | 'info'
 */
(function () {
  'use strict';

  window.GUA = window.GUA || {};

  var _toastEl   = document.getElementById('gua-toast');
  var _toastIcon = document.getElementById('toast-icon');
  var _toastMsg  = document.getElementById('toast-msg');
  var _toastTimer = null;

  var TOAST_TYPES = {
    success: {
      bg: '#1c1917', color: '#fff', iconColor: '#6ee7b7',
      d: 'M4.5 12.75 10.5 18.75 19.5 6.75'
    },
    error: {
      bg: '#7f1d1d', color: '#fff', iconColor: '#fca5a5',
      d: 'M6 18 18 6M6 6l12 12'
    },
    info: {
      bg: '#1c3557', color: '#fff', iconColor: '#93c5fd',
      d: 'M11.25 11.25l.041-.02a.75.75 0 0 1 1.063.852l-.708 2.836a.75.75 0 0 0 1.063.853l.041-.021M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0zm-9-3.75h.008v.008H12V8.25z'
    }
  };

  GUA.toast = function (msg, type, duration) {
    type     = type || 'success';
    duration = duration || 3500;
    var cfg  = TOAST_TYPES[type] || TOAST_TYPES.info;

    Object.assign(_toastEl.style, { backgroundColor: cfg.bg, color: cfg.color });
    _toastIcon.style.color = cfg.iconColor;
    _toastIcon.innerHTML   = '<path stroke-linecap="round" stroke-linejoin="round" d="' + cfg.d + '"/>';
    _toastMsg.textContent  = msg;

    _toastEl.style.opacity   = '1';
    _toastEl.style.transform = 'translateX(-50%) translateY(0)';

    clearTimeout(_toastTimer);
    _toastTimer = setTimeout(function () {
      _toastEl.style.opacity   = '0';
      _toastEl.style.transform = 'translateX(-50%) translateY(0.5rem)';
    }, duration);
  };
})();