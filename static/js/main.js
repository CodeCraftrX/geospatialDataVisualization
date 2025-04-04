$(document).ready(function() {
    // Initialize Select2 with placeholders
    $('#tableSelect').select2({
        placeholder: "Select a table",
        allowClear: true
    });
    
    $('#independentSelect').select2({
        placeholder: "Select dependent variable",
        allowClear: true
    });
    
    $('#dependentsSelect').select2({
        placeholder: "Select independent variables",
        multiple: true,
        allowClear: true
    });

    // Fetch all tables when page loads
    fetch('/get-tables')
        .then(response => response.json())
        .then(data => {
            const tableSelect = $('#tableSelect');
            tableSelect.empty();
            tableSelect.append(new Option('', '', true, true));
            data.tables.forEach(table => {
                tableSelect.append(new Option(table, table));
            });
        });

    // Handle table selection change
    $('#tableSelect').on('change', function() {
        const selectedTable = $(this).val();
        if (selectedTable) {
            // Fetch columns for selected table
            fetch(`/get-columns?table=${selectedTable}`)
                .then(response => response.json())
                .then(data => {
                    const independentSelect = $('#independentSelect');
                    const dependentsSelect = $('#dependentsSelect');
                    
                    // Clear existing options
                    independentSelect.empty();
                    dependentsSelect.empty();
                    
                    // Add empty option for placeholder
                    independentSelect.append(new Option('', '', true, true));
                    
                    // Add columns to both dropdowns
                    data.columns.forEach(column => {
                        independentSelect.append(new Option(column, column));
                        dependentsSelect.append(new Option(column, column));
                    });
                    
                    // Trigger change to refresh Select2
                    independentSelect.trigger('change');
                    dependentsSelect.trigger('change');
                });
        }
    });

    // Handle form submission
    $('form').on('submit', function(e) {
        e.preventDefault();
        
        const table = $('#tableSelect').val();
        const independent = $('#independentSelect').val();
        const dependents = $('#dependentsSelect').val().join(',');

        fetch(`/visualize?table=${table}&independent=${independent}&dependents=${dependents}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const currentMap = $('#current-map');
                    currentMap.attr('src', data.maps[0]);
                    currentMap.show();

                    const tbody = $('#maps-table-body');
                    const mapName = data.maps[0].split('/').pop();
                    const row = `
                        <tr>
                            <td>${mapName}</td>
                            <td>${data.bandwidth.toFixed(2)}</td>
                            <td><a href="${data.maps[0]}" target="_blank">View Map</a></td>
                        </tr>
                    `;
                    tbody.append(row);
                }
            })
            .catch(error => console.error('Error:', error));
    });
}); 