$(document).ready(function () {
  console.log('🟢 [DT] init-datatable.js cargado');
  // ========== PERSISTENCIA DE BÚSQUEDA CON localStorage ==========
  var STORAGE_KEY = 'dt_listpass_state';

  function saveState(search, length, page) {
    try {
      var state = { search: search || '', length: length || 10, page: page || 0, ts: Date.now() };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      console.log('💾 [DT] Estado guardado');
    } catch (e) { console.error('❌ [DT] Error guardando estado:', e); }
  }

  function loadState() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        var state = JSON.parse(raw);
        return state;
      }
    } catch (e) { console.error('❌ [DT] Error cargando estado:', e); }
    return null;
  }

  var statusColIndex = null;
  var colIndexMap = {};
  var table = null;

  // determine DataTables language file from cookie (django_language) or browser
  function getCookie(name) {
    const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return v ? decodeURIComponent(v.pop()) : null;
  }

  const userLang = (getCookie('django_language') || navigator.language || 'en').toLowerCase();
  let dtLangUrl = '/static/lib/DataTables-1.13.1/english.txt'; // fallback
  console.log('🌐 [DT] Idioma detectado:', userLang);
  if (userLang.startsWith('es')) {
    dtLangUrl = '/static/lib/DataTables-1.13.1/spanish.txt';
  } else if (userLang.startsWith('en')) {
    dtLangUrl = '/static/lib/DataTables-1.13.1/english.txt';
  } else {
    // try a file based on language code (e.g. 'fr' -> 'french.txt')
    const code = userLang.split('-')[0];
    dtLangUrl = '/static/lib/DataTables-1.13.1/' + code + '.txt';
  }
  console.log('🌐 [DT] Usando fichero de idioma:', dtLangUrl);

  function createTableWithLanguage(languageOption) {
    table = $('#data').DataTable({
      responsive: false,
      colReorder: true,
      order: [],
      ordering: false,
      // State persistence handled manually (minimal payload in cookie)
      scrollX: true,
      dom: 'Rlfrtip',
      autoWidth: false,
      lengthMenu: [[10, 25, 50, 100, 250, 500, -1], [10, 25, 50, 100, 250, 500, "All"]],
      language: languageOption,
      createdRow: function (row, data, dataIndex) {
        if (statusColIndex !== null) {
          const tempDiv = document.createElement('div');
          tempDiv.innerHTML = data[statusColIndex];
          const statusText = tempDiv.textContent.toLowerCase();

          $(row).removeClass('table-warning table-primary table-success');

          // Map stage text to row color: pendiente -> danger, análisis -> warning, en proceso -> primary, implementado -> success
          if (statusText.includes("pendiente")) {
            $(row).addClass('table-danger');
          } else if (statusText.includes("análisis") || statusText.includes("analisis")) {
            $(row).addClass('table-warning');
          } else if (statusText.includes("en proceso")) {
            $(row).addClass('table-primary');
          } else if (statusText.includes("implementado")) {
            $(row).addClass('table-success');
          }
        }
      }
    });

    // expose table for external adjustments and ensure columns recalc on draw
    window.passTable = table;

    // attach previous listeners that rely on `table`
    table.on('draw', function () {
      try { table.columns.adjust(); } catch (e) { console.warn('passTable adjust failed', e); }
    });

    // Guardar en cada cambio de búsqueda, paginación o longitud
    table.on('search.dt length.dt page.dt', function (e) {
      saveCurrentState();
    });

    // Restaurar estado después de que DataTables termine de inicializarse
    table.on('init.dt', function () {
      console.log('🚀 [DT] init.dt disparado - llamando restoreState()');
      restoreState();
    });

    return table;
  }

  // Fetch language file first to debug failures and avoid silent network errors
  fetch(dtLangUrl, { cache: 'no-cache' })
    .then(function (resp) {
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      return resp.json();
    })
    .then(function (langObj) {
      console.log('🌐 [DT] Archivo de idioma cargado');
      // pass the object directly so DataTables doesn't re-fetch
      window.passTable = createTableWithLanguage(langObj);
    })
    .catch(function (err) {
      console.warn('⚠️ [DT] No se pudo cargar el fichero de idioma', dtLangUrl);
      // fallback: initialize table with empty language (DataTables will use defaults)
      window.passTable = createTableWithLanguage({});
    });

  // ========== RESTAURAR ESTADO AL INICIAR ==========
  function restoreState() {
    console.log('🔄 [DT] restoreState() llamado');
    var state = loadState();
    if (state) {
      console.log('🔄 [DT] Restaurando búsqueda:', state.search);
      if (state.search) {
        table.search(state.search);
        // También actualizar el input visual
        $('div.dataTables_filter input').val(state.search);
      }
      if (typeof state.length === 'number') {
        table.page.len(state.length);
      }
      if (typeof state.page === 'number') {
        table.page(state.page);
      }
      table.draw(false);
    } else {
      console.log('🔄 [DT] No hay estado guardado para restaurar');
    }
  }

  // ========== GUARDAR ESTADO EN CAMBIOS ==========
  function saveCurrentState() {
    try {
      var info = table.page.info();
      var search = table.search();
      console.log('🔔 [DT] saveCurrentState - search:', search, 'page:', info.page, 'length:', info.length);
      saveState(search, info.length, info.page);
    } catch (e) { console.error('❌ [DT] Error en saveCurrentState:', e); }
  }

  // (event bindings are attached when the table is created)

  // ========== MANEJAR BOTÓN ATRÁS (BFCache) ==========
  window.addEventListener('pageshow', function (ev) {
    if (ev.persisted) {
      restoreState();
    }
  });

  

  // Mapear columnas por data-colname
  $('#data thead th').each(function (index) {
    var colname = $(this).data('colname');
    if (colname) {
      colIndexMap[colname] = index;
      // detect stage column (replacing legacy implementation_status)
      if (colname === 'stage' || colname === 'implementation_status') {
        statusColIndex = index;
      }
    }
  });

  // Filtro dinámico por select (choices, booleanos, foreign keys)
  $('.filter-choice').on('change', function () {
    var colname = $(this).data('colname');
    var value = $(this).val();
    var colIndex = colIndexMap[colname];

    if (colIndex !== undefined) {
      table.column(colIndex).search(value).draw();
    }
  });

// Filtros por fechas
let filtrosFecha = {};  // Variable global

// Captura cambios en inputs de fecha
$('.filtro-fecha').on('change', function () {
  filtrosFecha = {}; // Reset filtros

  $('.filtro-fecha').each(function () {
    const colname = $(this).data('colname');
    const range = $(this).data('range');
    const value = $(this).val();

    //console.log(`📥 Input fecha cambiado → Columna: ${colname}, Rango: ${range}, Valor: ${value}`);

    if (!filtrosFecha[colname]) filtrosFecha[colname] = {};
    filtrosFecha[colname][range] = value;
  });

  //console.log('📊 Filtros armados:', filtrosFecha);

  table.draw(); // Redibuja con los filtros aplicados
});

// Filtro de fechas para DataTables
$.fn.dataTable.ext.search.push(function (settings, data, dataIndex) {
  for (let colname in filtrosFecha) {
    const colIndex = colIndexMap[colname];
    if (colIndex === undefined) continue;

    const rawDate = data[colIndex]?.trim();
    if (!rawDate || !/^\d{4}-\d{2}-\d{2}$/.test(rawDate)) return false;

    const [year, month, day] = rawDate.split('-');
    const rowDate = resetTime(new Date(year, month - 1, day));

    const minRaw = filtrosFecha[colname].min;
    const maxRaw = filtrosFecha[colname].max;

    const min = minRaw && /^\d{4}-\d{2}-\d{2}$/.test(minRaw) ? resetTime(new Date(minRaw)) : null;
    const max = maxRaw && /^\d{4}-\d{2}-\d{2}$/.test(maxRaw) ? resetTime(new Date(maxRaw)) : null;

    //console.log(`🔎 Comparando fila: ${rowDate.toISOString()} | Min: ${min?.toISOString()} | Max: ${max?.toISOString()}`);

    if ((min && rowDate < min) || (max && rowDate > max)) {
      //console.log(`❌ Fila filtrada fuera de rango`);
      return false;
    }
  }

  //console.log(`✅ Fila pasa filtro`);
  return true;
});

// Función para eliminar hora de un objeto Date
function resetTime(date) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}



    if (table) table.draw();
  });

