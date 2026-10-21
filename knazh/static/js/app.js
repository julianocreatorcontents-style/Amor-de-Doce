/* KNAZH — melhorias progressivas. O site funciona sem JavaScript; aqui só aprimoramos. */
(function () {
  'use strict';
  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';

  /* Menu mobile */
  var toggle = document.querySelector('[data-menu-toggle]');
  var menu = document.querySelector('[data-menu]');
  function setMenu(open) {
    if (!toggle || !menu) return;
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    toggle.querySelector('.sr-only').textContent = open ? 'Fechar menu' : 'Abrir menu';
    toggle.querySelector('use').setAttribute('href', open ? '#i-close' : '#i-menu');
    menu.classList.toggle('is-open', open);
  }
  if (toggle && menu) {
    toggle.addEventListener('click', function () { setMenu(toggle.getAttribute('aria-expanded') !== 'true'); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') { setMenu(false); toggle.focus(); }
    });
    document.addEventListener('click', function (e) {
      if (toggle.getAttribute('aria-expanded') === 'true' && !menu.contains(e.target) && !toggle.contains(e.target)) setMenu(false);
    });
  }

  /* Avisos (toasts) */
  var toasts = document.querySelector('[data-toasts]');
  function showToast(msg, kind) {
    if (!toasts) return;
    var p = document.createElement('p');
    p.className = 'toast toast--' + (kind || 'success');
    p.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    p.textContent = msg;
    toasts.appendChild(p);
    setTimeout(function () { p.remove(); }, 5000);
  }
  document.querySelectorAll('.toast').forEach(function (t) { setTimeout(function () { t.remove(); }, 7000); });

  function setCount(n) {
    document.querySelectorAll('[data-cart-count]').forEach(function (el) { el.textContent = n; el.hidden = !n; });
  }

  /* Adicionar ao carrinho sem recarregar a página */
  function bindAdd(form) {
    form.addEventListener('submit', function (e) {
      if (!window.fetch) return;
      e.preventDefault();
      var btn = form.querySelector('button[type="submit"]');
      if (btn) btn.disabled = true;
      fetch(form.action, { method: 'POST', body: new FormData(form), headers: { 'X-Requested-With': 'fetch', 'X-CSRFToken': csrf }, credentials: 'same-origin' })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
        .then(function (res) { showToast(res.data.message, res.ok ? 'success' : 'error'); if (res.ok) setCount(res.data.count); })
        .catch(function () { form.submit(); })
        .finally(function () { if (btn) btn.disabled = false; });
    });
  }
  document.querySelectorAll('.js-add-form, [data-buy-form]').forEach(bindAdd);

  /* Quantidade na página de produto */
  var qty = document.querySelector('.qty__input');
  if (qty) {
    var min = +qty.min || 1, max = +qty.max || 99;
    var clamp = function (v) { v = parseInt(v, 10); if (isNaN(v)) v = min; return Math.max(min, Math.min(max, v)); };
    document.querySelector('[data-qty-dec]').addEventListener('click', function () { qty.value = clamp(+qty.value - 1); });
    document.querySelector('[data-qty-inc]').addEventListener('click', function () { qty.value = clamp(+qty.value + 1); });
    qty.addEventListener('change', function () { qty.value = clamp(qty.value); });
  }

  /* Filtros: aplica ao mudar; no celular o painel começa recolhido */
  var fp = document.querySelector('[data-filters]');
  if (fp && window.matchMedia('(max-width: 899px)').matches) fp.removeAttribute('open');
  document.querySelectorAll('[data-autosubmit]').forEach(function (f) {
    f.classList.add('is-enhanced');
    f.addEventListener('change', function () { f.submit(); });
  });

  /* Evita envio duplicado de formulários */
  document.querySelectorAll('form[data-once]').forEach(function (f) {
    f.addEventListener('submit', function () {
      var b = f.querySelector('button[type="submit"]');
      if (b) setTimeout(function () { b.disabled = true; b.setAttribute('aria-busy', 'true'); }, 0);
    });
  });

  /* Busca nas dúvidas frequentes */
  var fq = document.querySelector('[data-faq-search]');
  if (fq) {
    var norm = function (s) { return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase(); };
    fq.addEventListener('input', function () {
      var q = norm(fq.value.trim()), any = false;
      document.querySelectorAll('[data-faq-item]').forEach(function (it) {
        var hit = !q || norm(it.textContent).indexOf(q) !== -1;
        it.hidden = !hit; if (hit) any = true;
      });
      document.querySelectorAll('[data-faq-group]').forEach(function (g) {
        g.hidden = !g.querySelector('[data-faq-item]:not([hidden])');
      });
      document.querySelector('[data-faq-none]').hidden = any;
    });
  }
})();
