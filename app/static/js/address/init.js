/**
 * static/js/address/init.js
 * Page initialization — runs after all other modules load.
 * - Bridges Flask flash messages → GUA.toast
 * - Auto-opens modal on checkout redirect with no addresses
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {

    // ── FIX: Flash message → toast bridge ──────────────────────
    // window.__GUA_FLASH__ is injected by the Jinja2 template
    var flashes = window.__GUA_FLASH__ || [];
    if (flashes.length > 0) {
      // Stagger multiple flash messages slightly
      flashes.forEach(function (flash, i) {
        setTimeout(function () {
          GUA.toast(flash.msg, flash.type);
        }, i * 400);
      });
    }

    // ── Auto-open modal on checkout redirect (no addresses) ─────
    // This condition is injected as a data attribute to avoid inline Jinja in JS
    var page = document.getElementById('address-list');
    var hasNext = new URLSearchParams(window.location.search).get('next');
    var isEmpty = !page || page.children.length === 0;

    if (hasNext && isEmpty) {
      // Small delay so toast (if any) appears first
      setTimeout(function () { GUA.modal.open('add'); }, 200);
    }

  });

})();