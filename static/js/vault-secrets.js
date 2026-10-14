(function () {
  'use strict';
  var timer;
  function notify(message) {
    var toast = document.querySelector('.vault-toast');
    if (!toast) return;
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(timer);
    timer = setTimeout(function () { toast.hidden = true; }, 3200);
  }
  document.addEventListener('click', async function (event) {
    var button = event.target.closest('[data-vault-action]');
    if (!button) return;
    var box = button.closest('.vault-secret');
    var url = button.dataset.url || (box && box.dataset.url);
    var field = button.dataset.field || 'password';
    var csrf = document.querySelector('.vault-csrf input[name="csrfmiddlewaretoken"]');
    if (!url || !csrf) return;
    button.disabled = true;
    try {
      var response = await fetch(url, {method: 'POST', credentials: 'same-origin', cache: 'no-store', headers: {'X-CSRFToken': csrf.value, 'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}, body: new URLSearchParams({field: field}).toString()});
      if (!response.ok) throw new Error('No se pudo acceder a la credencial.');
      var data = await response.json();
      var value = data.value;
      if (typeof value !== 'string') throw new Error('La credencial no está disponible.');
      if (button.dataset.vaultAction === 'copy') {
        await navigator.clipboard.writeText(value);
        notify(field === 'username' ? 'Usuario copiado' : 'Contraseña copiada');
      } else if (box) {
        var target = box.querySelector('[data-secret-field="' + field + '"]');
        target.textContent = value;
        notify('Visible durante 20 segundos');
        setTimeout(function () { target.textContent = '••••••••'; }, 20000);
      }
    } catch (error) { notify(error.message || 'No se pudo copiar.'); }
    finally { button.disabled = false; }
  });
}());
