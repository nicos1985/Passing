(() => {
  const form = document.getElementById('support-chat-form');
  if (!form) return;
  const portal = form.querySelector('[name="portal"]');
  const dialog = form.querySelector('[name="dialog_id"]');
  const label = form.querySelector('[name="label"]');
  const link = form.querySelector('[name="link_url"]');
  const ignored = form.querySelector('[name="ignored_sender_ids"]');
  const picker = document.getElementById('bitrix-group-picker');
  const open = document.getElementById('bitrix-open-group');
  const origins = JSON.parse(document.getElementById('bitrix-portal-origins').textContent);
  const groupPattern = /^chat[1-9][0-9]*$/;
  const states = Object.fromEntries(['groups', 'people'].map(kind => [kind, {
    sequence: 0, controller: null, items: new Map(), nextOffset: null, nextCursor: null,
    query: '', dialog: '', mode: '',
  }]));
  let autoLabel = '';
  const status = (kind, text, error = false) => {
    const element = document.getElementById(`bitrix-${kind}-status`);
    element.textContent = text;
    element.classList.toggle('text-danger', error);
  };
  function busy(kind, value) {
    form.querySelectorAll(`[data-api-button="${kind}"]`).forEach(button => { button.disabled = value; });
  }
  function selectedIds() {
    return new Set(ignored.value.split(',').map(value => value.trim()).filter(value => /^[1-9][0-9]*$/.test(value)));
  }
  function syncPeople() {
    const selected = selectedIds();
    document.querySelectorAll('#bitrix-people-results input').forEach(input => { input.checked = selected.has(input.value); });
    document.getElementById('bitrix-ignored-count').textContent = `${selected.size} de 30 personas seleccionadas para ignorar`;
  }
  function updateLink() {
    open.hidden = true;
    open.removeAttribute('href');
    if (!origins[portal.value] || !groupPattern.test(dialog.value.trim())) return;
    try {
      const origin = new URL(origins[portal.value]);
      const generated = new URL(`/online/?IM_DIALOG=${dialog.value.trim()}`, origin);
      const target = link.value.trim() ? new URL(link.value.trim()) : generated;
      if (target.protocol !== 'https:' || target.origin !== origin.origin || target.username || target.password || target.hash || target.pathname.includes('/rest/') || target.search.includes('/rest/')) return;
      open.href = target.href;
      open.hidden = false;
    } catch (_) { /* Wait until the manually entered link is valid. */ }
  }
  function reset(kind) {
    const state = states[kind];
    state.sequence++;
    state.controller?.abort();
    state.items.clear();
    state.nextOffset = null;
    state.nextCursor = null;
    document.getElementById(`bitrix-more-${kind}`).hidden = true;
    if (kind === 'groups') picker.replaceChildren(new Option('Consultá los grupos para elegir uno', ''));
    else document.getElementById('bitrix-people-results').replaceChildren();
    busy(kind, false);
  }
  function renderGroups() {
    const current = dialog.value.trim();
    picker.replaceChildren(new Option('Elegí un grupo por nombre e ID', ''));
    for (const item of states.groups.items.values()) picker.add(new Option(`${item.name} · ${item.id}`, item.id));
    if (states.groups.items.has(current)) picker.value = current;
  }
  function renderPeople() {
    const results = document.getElementById('bitrix-people-results');
    results.replaceChildren();
    for (const item of states.people.items.values()) {
      const row = document.createElement('label');
      row.className = 'directory-person';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.className = 'form-check-input mt-0';
      checkbox.value = item.id;
      const text = document.createElement('span');
      text.textContent = item.name;
      const id = document.createElement('small');
      id.textContent = `ID ${item.id}`;
      text.append(id);
      row.append(checkbox, text);
      checkbox.addEventListener('change', () => {
        const selected = selectedIds();
        if (checkbox.checked && !selected.has(item.id) && selected.size >= 30) {
          checkbox.checked = false;
          status('people', 'Podés ignorar hasta 30 personas por grupo.', true);
          return;
        }
        if (checkbox.checked) selected.add(item.id); else selected.delete(item.id);
        ignored.value = [...selected].join(',');
        syncPeople();
      });
      results.append(row);
    }
    syncPeople();
  }
  async function load(kind, mode, more = false) {
    if (!/^[1-9][0-9]*$/.test(portal.value)) { status(kind, 'Elegí primero un portal guardado en Passing.', true); return; }
    const state = states[kind];
    const query = more ? state.query : mode === 'search' ? document.getElementById(kind === 'groups' ? 'bitrix-group-query' : 'bitrix-person-query').value.trim() : '';
    const currentDialog = more ? state.dialog : dialog.value.trim();
    if (mode === 'search' && query.length < 2) { status(kind, 'Escribí al menos dos letras para buscar.', true); return; }
    if (kind === 'people' && !query && !groupPattern.test(currentDialog)) { status(kind, 'Elegí o ingresá primero el ID del grupo, por ejemplo chat123.', true); return; }
    if (more && state.nextOffset === null && !state.nextCursor) return;
    state.controller?.abort();
    const sequence = ++state.sequence;
    const controller = new AbortController();
    state.controller = controller;
    const params = new URLSearchParams({ kind, query });
    if (kind === 'people' && !query) params.set('dialog', currentDialog);
    if (more && state.nextOffset !== null) params.set('offset', state.nextOffset);
    if (more && state.nextCursor) params.set('cursor', state.nextCursor);
    if (!more) {
      state.items.clear(); state.nextOffset = null; state.nextCursor = null;
      document.getElementById(`bitrix-more-${kind}`).hidden = true;
      if (kind === 'groups') renderGroups(); else renderPeople();
    }
    state.query = query; state.dialog = currentDialog; state.mode = mode;
    busy(kind, true);
    status(kind, 'Consultando Bitrix24…');
    const url = form.dataset.directoryUrl.replace('/0/directory/', `/${portal.value}/directory/`);
    try {
      const response = await fetch(url, {
        method: 'POST', credentials: 'same-origin', cache: 'no-store', signal: controller.signal,
        headers: { 'X-CSRFToken': form.querySelector('[name="csrfmiddlewaretoken"]').value, Accept: 'application/json' },
        body: params,
      });
      const data = await response.json().catch(() => ({}));
      if (sequence !== state.sequence) return;
      if (!response.ok) throw new Error(data.error || 'No se pudo consultar Bitrix24. Revisá tus permisos y el webhook del portal.');
      for (const item of data.items || []) state.items.set(String(item.id), item);
      state.nextOffset = data.next_offset ?? null;
      state.nextCursor = data.next_cursor || null;
      if (kind === 'groups') renderGroups(); else renderPeople();
      const moreButton = document.getElementById(`bitrix-more-${kind}`);
      moreButton.hidden = state.nextOffset === null && !state.nextCursor;
      status(kind, state.items.size ? `${state.items.size} ${kind === 'groups' ? 'grupos' : 'personas'} disponibles.${kind === 'groups' && !query ? ' Si falta uno, buscá por nombre.' : ''}` : 'No se encontraron resultados. Probá otra búsqueda o verificá el acceso de la cuenta del webhook.');
    } catch (error) {
      if (error.name !== 'AbortError' && sequence === state.sequence) status(kind, error.message, true);
    } finally { if (sequence === state.sequence) busy(kind, false); }
  }
  document.getElementById('bitrix-recent-groups').addEventListener('click', () => load('groups', 'recent'));
  document.getElementById('bitrix-search-groups').addEventListener('click', () => load('groups', 'search'));
  document.getElementById('bitrix-chat-people').addEventListener('click', () => load('people', 'dialog'));
  document.getElementById('bitrix-search-people').addEventListener('click', () => load('people', 'search'));
  for (const kind of ['groups', 'people']) document.getElementById(`bitrix-more-${kind}`).addEventListener('click', () => load(kind, states[kind].mode, true));
  for (const [id, kind] of [['bitrix-group-query', 'groups'], ['bitrix-person-query', 'people']]) {
    document.getElementById(id).addEventListener('keydown', event => {
      if (event.key === 'Enter') { event.preventDefault(); load(kind, 'search'); }
    });
  }
  picker.addEventListener('change', () => {
    const item = states.groups.items.get(picker.value);
    if (!item) return;
    dialog.value = item.id;
    label.value = item.name;
    autoLabel = item.name;
    link.value = item.link;
    reset('people');
    updateLink();
    load('people', 'dialog');
  });
  portal.addEventListener('change', () => {
    reset('groups'); reset('people');
    dialog.value = ''; link.value = ''; ignored.value = '';
    if (label.value === autoLabel) label.value = '';
    status('groups', 'Consultá los grupos recientes o buscá por nombre.');
    status('people', 'Elegí un grupo o buscá una persona en el nuevo portal.');
    updateLink(); syncPeople();
  });
  dialog.addEventListener('input', () => { reset('people'); updateLink(); });
  link.addEventListener('input', updateLink);
  ignored.addEventListener('input', syncPeople);
  updateLink(); syncPeople();
})();
