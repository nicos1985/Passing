$(document).ready(function () {
  var statusColIndex = null;
  var colIndexMap = {};

  var table = $('#data').DataTable({
    responsive: false,
    colReorder: true,
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
        tempDiv.innerHTML = data[statusColIndex];  // Extraer texto en caso de HTML
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

  // Obtener índices de columna por data-colname
  $('#data thead th').each(function (index) {
    var colname = $(this).data('colname');
    if (colname) {
      colIndexMap[colname] = index;
      if (colname === 'implementation_status') {
        statusColIndex = index;
      }
    }
  });

  // Filtro genérico para selects de choices
  $('.filter-choice').on('change', function () {
    var colname = $(this).data('colname');
    var value = $(this).val();
    var colIndex = colIndexMap[colname];

    if (colIndex !== undefined) {
      table.column(colIndex).search(value).draw();
    }
  });

  // Filtro por vencimiento
  $('#filtroVencimiento').on('change', function () {
    var vencimientoIndex = colIndexMap['deadline'];
    var valor = $(this).val();

    $.fn.dataTable.ext.search = $.fn.dataTable.ext.search.filter(function (f) {
      return f.name !== 'vencimientoFilter';
    });

    if (valor) {
      $.fn.dataTable.ext.search.push({
        name: 'vencimientoFilter',
        fn: function (settings, data, dataIndex) {
          if (vencimientoIndex === undefined || statusColIndex === null) return true;

          var deadline = data[vencimientoIndex];
          var status = data[statusColIndex];

          var today = new Date();
          var deadlineDate = new Date(deadline);

          const temp = document.createElement('div');
          temp.innerHTML = status;
          const statusText = temp.textContent.toLowerCase();

          if (valor === 'vencidos_no_completados') {
            return deadlineDate < today && !statusText.includes("completado");
          } else if (valor === 'no_vencidos') {
            return deadlineDate >= today;
          } else if (valor === 'completados') {
            return statusText.includes("completado");
          }
          return true;
        }
      });
    }

    table.draw();
  });
});
