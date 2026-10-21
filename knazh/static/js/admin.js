/* KNAZH — painel administrativo. Melhorias progressivas: sem JavaScript tudo continua funcionando
   (a exclusão usa a tela de confirmação; o envio da foto funciona sem pré-visualização). Nada é enviado
   ao servidor até o formulário ser salvo. Compatível com a CSP do site (sem inline, sem blob:). */
(function () {
  'use strict';

  /* Avisos temporários */
  document.querySelectorAll('.toast').forEach(function (t) { setTimeout(function () { t.remove(); }, 7000); });

  /* Evita envio duplicado */
  document.querySelectorAll('form[data-once]').forEach(function (f) {
    f.addEventListener('submit', function () {
      var b = f.querySelector('button[type="submit"]');
      if (b) setTimeout(function () { b.disabled = true; b.setAttribute('aria-busy', 'true'); }, 0);
    });
  });

  /* Confirmação de exclusão em diálogo acessível (<dialog>: foco preso, Esc fecha) */
  var dialog = document.querySelector('[data-delete-dialog]');
  if (dialog && typeof dialog.showModal === 'function') {
    var form = dialog.querySelector('[data-delete-form]');
    var nameEl = dialog.querySelector('[data-delete-name]');
    var opener = null;
    document.querySelectorAll('[data-delete]').forEach(function (link) {
      link.addEventListener('click', function (e) {
        e.preventDefault();
        opener = link;
        form.action = link.getAttribute('href');   /* a mesma URL aceita POST (exclusão) e GET (tela de confirmação) */
        nameEl.textContent = link.getAttribute('data-product-name') || '';
        dialog.showModal();
        var cancel = dialog.querySelector('[data-dialog-cancel]');
        if (cancel) cancel.focus();                 /* foco inicial no botão seguro */
      });
    });
    dialog.querySelector('[data-dialog-cancel]').addEventListener('click', function () { dialog.close(); });
    dialog.addEventListener('click', function (e) { if (e.target === dialog) dialog.close(); });
    dialog.addEventListener('close', function () { if (opener) opener.focus(); });
    form.addEventListener('submit', function () {
      var b = form.querySelector('button[type="submit"]');
      if (b) setTimeout(function () { b.disabled = true; b.setAttribute('aria-busy', 'true'); }, 0);
    });
  }

  /* Confirmação de conceder/remover acesso administrativo (<dialog>). Sem JavaScript, o link abre a tela de
     confirmação do servidor. A permissão é sempre validada no servidor; isto é só a etapa de confirmação. */
  var adm = document.querySelector('[data-admin-dialog]');
  if (adm && typeof adm.showModal === 'function') {
    var aform = adm.querySelector('[data-admin-form]');
    var atitle = adm.querySelector('[data-admin-title]');
    var atext = adm.querySelector('[data-admin-text]');
    var amanage = adm.querySelector('[data-admin-manage]');
    var aconfirm = adm.querySelector('[data-admin-confirm]');
    var aopener = null;
    document.querySelectorAll('[data-admin-action]').forEach(function (link) {
      link.addEventListener('click', function (e) {
        e.preventDefault();
        aopener = link;
        var grant = link.getAttribute('data-admin-action') === 'grant';
        var name = link.getAttribute('data-user-name') || '';
        aform.action = link.getAttribute('href');
        amanage.hidden = !grant;
        amanage.querySelector('input').checked = false;
        atitle.textContent = grant ? 'Tornar administrador(a)?' : 'Remover acesso administrativo?';
        atext.textContent = grant
          ? '“' + name + '” passará a acessar o painel e poderá cadastrar, editar e excluir produtos da loja.'
          : '“' + name + '” perderá o acesso ao painel. A conta continua existindo como cliente comum.';
        aconfirm.textContent = grant ? 'Conceder acesso' : 'Remover acesso';
        aconfirm.className = 'btn ' + (grant ? 'btn--primary' : 'btn--danger');
        aconfirm.disabled = false; aconfirm.removeAttribute('aria-busy');
        adm.showModal();
        adm.querySelector('[data-dialog-cancel]').focus();   /* foco inicial no botão seguro */
      });
    });
    adm.querySelector('[data-dialog-cancel]').addEventListener('click', function () { adm.close(); });
    adm.addEventListener('click', function (e) { if (e.target === adm) adm.close(); });
    adm.addEventListener('close', function () { if (aopener) aopener.focus(); });
    aform.addEventListener('submit', function () { setTimeout(function () { aconfirm.disabled = true; aconfirm.setAttribute('aria-busy', 'true'); }, 0); });
  }

  /* Pré-visualização instantânea da foto (FileReader -> data:, permitido pela CSP). Só conveniência:
     o servidor revalida tipo, tamanho e conteúdo de qualquer forma. */
  var box = document.querySelector('[data-photo]');
  if (box && window.FileReader) {
    var input = box.querySelector('[data-image-input]');
    var img = box.querySelector('[data-image-preview]');
    var empty = box.querySelector('[data-image-empty]');
    var status = box.querySelector('[data-photo-status]');
    var errEl = box.querySelector('[data-photo-error]');
    var reset = box.querySelector('[data-photo-reset]');
    var maxBytes = parseInt(box.getAttribute('data-max-bytes'), 10) || 0;
    var original = img.getAttribute('data-original-src') || '';
    var ok = { 'image/jpeg': 1, 'image/png': 1, 'image/webp': 1 };
    var originalStatus = status.textContent;

    function showError(msg) { errEl.textContent = msg; errEl.hidden = !msg; }
    function restore() {
      input.value = '';
      showError('');
      if (original) { img.src = original; img.hidden = false; if (empty) empty.hidden = true; }
      else { img.hidden = true; img.removeAttribute('src'); if (empty) empty.hidden = false; }
      status.textContent = originalStatus;
      if (reset) reset.hidden = true;
    }
    input.addEventListener('change', function () {
      var file = input.files && input.files[0];
      showError('');
      if (!file) { restore(); return; }
      if (!ok[file.type]) { restore(); showError('Formato não permitido. Escolha uma imagem JPG, PNG ou WebP.'); return; }
      if (maxBytes && file.size > maxBytes) { restore(); showError('A imagem é grande demais. O tamanho máximo é ' + Math.round(maxBytes / 1048576) + ' MiB.'); return; }
      var reader = new FileReader();
      reader.onload = function () {
        img.src = reader.result; img.alt = 'Pré-visualização da nova foto'; img.hidden = false;
        if (empty) empty.hidden = true;
        status.textContent = 'Nova foto (ainda não salva)';
        if (reset) reset.hidden = false;
      };
      reader.onerror = function () { restore(); showError('Não foi possível ler esse arquivo.'); };
      reader.readAsDataURL(file);
    });
    if (reset) reset.addEventListener('click', function () { restore(); input.focus(); });
  }

  /* Foco no resumo de erros do formulário */
  var alertBox = document.querySelector('[data-form-alert]');
  if (alertBox) alertBox.focus();
})();
