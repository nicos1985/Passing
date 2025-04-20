
  $(document).ready(function () {
    $('#data').DataTable({
      responsive: true,
      colReorder: true,
      dom: 'Rlfrtip',
      autoWidth: false,
      lengthMenu: [[10, 25, 50, 100, 250, 500, -1], [10, 25, 50, 100, 250, 500, "All"]],
      language: {
        url: '/static/lib/DataTables-1.13.1/spanish.txt'
      }
    });
  });
