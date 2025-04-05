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
        const dependents = $('#dependentsSelect').val();  // This gets the array of selected dependent variables

        fetch(`/visualize?table=${table}&independent=${independent}&dependents=${dependents.join(',')}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const tbody = $('#maps-table-body');
                    
                    // Add original map row
                    const mapRow = `
                        <tr>
                            <td>Original Map</td>
                            <td>Generated Map</td>
                            <td><a href="${data.maps[0]}" target="_blank">View Map</a></td>
                        </tr>
                    `;
                    
                    // Add GWR results row
                    const gwrRow = `
                        <tr>
                            <td>GWR Results</td>
                            <td>Bandwidth: ${data.bandwidth.toFixed(2)}</td>
                            <td><a href="#" onclick="showGWRResults()">View Results</a></td>
                        </tr>
                    `;
                    
                    // Add GWR Summary row
                    const gwrSummaryRow = `
                        <tr>
                            <td>GWR Summary</td>
                            <td>GWR Model Statistics</td>
                            <td><a href="${data.gwr_summary_file}" target="_blank">View GWR Summary</a></td>
                        </tr>
                    `;
                    
                    // Add MGWR results row
                    const mgwrRow = `
                        <tr>
                            <td>MGWR Results</td>
                            <td>Bandwidths: ${data.mgwr_bandwidth.map(bw => bw.toFixed(2)).join(', ')}</td>
                            <td><a href="#" onclick="showMGWRResults()">View Results</a></td>
                        </tr>
                    `;

                    // Add MGWR Summary row
                    const mgwrSummaryRow = `
                        <tr>
                            <td>MGWR Summary</td>
                            <td>MGWR Model Statistics</td>
                            <td><a href="${data.mgwr_summary_file}" target="_blank">View MGWR Summary</a></td>
                        </tr>
                    `;
                    
                    // Add Intercept comparison row
                    const interceptRow = `
                        <tr>
                            <td>Intercept Surface Comparison</td>
                            <td>GWR vs MGWR Intercept Parameters</td>
                            <td><a href="${data.maps[1]}" target="_blank">View Comparison Maps</a></td>
                        </tr>
                    `;
                    
                    // Add comparison rows only for selected variables
                    const selectedVarsRows = dependents.map((varName, index) => `
                        <tr>
                            <td>${varName} Surface Comparison</td>
                            <td>GWR vs MGWR ${varName} Parameters</td>
                            <td><a href="${data.maps[index + 2]}" target="_blank">View Comparison Maps</a></td>
                        </tr>
                    `).join('');
                    
                    // Append all rows in the desired order
                    tbody.empty();  // Clear existing rows
                    tbody.append(mapRow + gwrRow + gwrSummaryRow + mgwrRow + mgwrSummaryRow + interceptRow + selectedVarsRows);

                    if (data.summary) {
                        $('#model-summary').html(`
                            <h4>Model Summary</h4>
                            <p>Model Type: ${data.summary.model_type}</p>
                            <p>Observations: ${data.summary.observations}</p>
                            <p>Covariates: ${data.summary.covariates}</p>
                        `);
                    }
                }
            })
            .catch(error => console.error('Error:', error));
    });

    // Add this function to handle MGWR Summary display
    function showMGWRSummary(summaryData) {
        const summary = JSON.parse(decodeURIComponent(summaryData));
        
        // Create modal or popup to display the summary
        const summaryWindow = window.open('', 'MGWR Summary', 'width=800,height=600');
        summaryWindow.document.write(`
            <html>
            <head>
                <title>MGWR Summary Results</title>
                <style>
                    body { font-family: monospace; white-space: pre; padding: 20px; }
                    table { border-collapse: collapse; width: 100%; }
                    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                    th { background-color: #f5f5f5; }
                </style>
            </head>
            <body>
                <h2>Multi-Scale Geographically Weighted Regression (MGWR) Results</h2>
                ${summary.text}
            </body>
            </html>
        `);
    }
}); 