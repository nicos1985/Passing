$(document).ready(function () {
  var statusColIndex = null;
  var colIndexMap = {};

  var table = $('#data').DataTable({
    responsive: false,
    colReorder: true,
    order: [],
    ordering: false,
    scrollX: true,
    dom: 'Rlfrtip',
    autoWidth: false,
    lengthMenu: [[10, 25, 50, 100, 250, 500, -1], [10, 25, 50, 100, 250, 500, "All"]],
    language: {
      url: '/static/lib/DataTables-1.13.1/spanish.txt'
    },
    createdRow: function (row, data, dataIndex) {
      if (statusColIndex !== null) {
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = data[statusColIndex];
        const statusText = tempDiv.textContent.toLowerCase();

        $(row).removeClass('table-warning table-primary table-success');

        if (statusText.includes("pendiente")) {
          $(row).addClass('table-warning');
        } else if (statusText.includes("en progreso")) {
          $(row).addClass('table-primary');
        } else if (statusText.includes("completado")) {
          $(row).addClass('table-success');
        }
      }
    }
  });

  // Mapear columnas por data-colname
  $('#data thead th').each(function (index) {
    var colname = $(this).data('colname');
    if (colname) {
      colIndexMap[colname] = index;
      if (colname === 'implementation_status') {
        statusColIndex = index;
      }
    }
  });

  // Filtro dinámico por select (choices, booleanos, foreign keys)
  $('.filter-choice').on('change', function () {
    var colname = $(this).data('colname');
    var value = $(this).val();
    var colIndex = colIndexMap[colname];

    console.log(`🟨 Filtro aplicado → Campo: ${colname}, Valor: "${value}", Columna #: ${colIndex}`);

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



    table.draw();
  });

