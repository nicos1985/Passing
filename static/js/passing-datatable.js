(function () {
  'use strict';
  if (!window.jQuery || !jQuery.fn.DataTable) return;
  jQuery('[data-passing-table]').each(function () {
    var table = this;
    if (jQuery.fn.DataTable.isDataTable(table)) return;
    var noSort = [];
    jQuery(table).find('thead th').each(function (index) {
      if (this.hasAttribute('data-no-sort')) noSort.push(index);
    });
    jQuery(table).DataTable({
      pageLength: 25,
      lengthMenu: [[10, 25, 50, 100], [10, 25, 50, 100]],
      order: [[Number(table.dataset.orderColumn || 0), 'asc']],
      columnDefs: [{targets: noSort, orderable: false, searchable: false}],
      autoWidth: false,
      language: {
        search: 'Buscar:', lengthMenu: 'Mostrar _MENU_', info: '_START_–_END_ de _TOTAL_',
        infoEmpty: 'Sin registros', infoFiltered: '(filtrados de _MAX_)', zeroRecords: 'No se encontraron resultados',
        emptyTable: 'No hay registros para mostrar', paginate: {first: 'Primera', last: 'Última', next: 'Siguiente', previous: 'Anterior'}
      }
    });
  });
}());
