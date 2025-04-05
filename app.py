from flask import Flask, render_template, request, jsonify
import psycopg2
import numpy as np
import libpysal as ps 
from mgwr.gwr import GWR, MGWR
from mgwr.sel_bw import Sel_BW
from mgwr.utils import shift_colormap, truncate_colormap
import geopandas as gp
import matplotlib
matplotlib.use('Agg')  # Use a non-interactive backend
import matplotlib.pyplot as plt
import matplotlib as mpl
import pandas as pd
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

app = Flask(__name__)

# Database configuration using environment variables
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "geoda_db"),
    "user": os.getenv("DB_USER", "geoda_user"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "pgsql.dataconn.net"),
    "port": os.getenv("DB_PORT", "5432")
}

def get_tables():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'updated'")
    tables = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return tables

def get_table_data(table_name):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Get columns (parameterized query)
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
        (table_name,)
    )
    columns = [row[0] for row in cur.fetchall()]

    # Get rows (schema-qualified table)
    cur.execute(f"SELECT * FROM updated.{table_name} LIMIT 10")
    rows = cur.fetchall()

    cur.close()
    conn.close()
    return columns, rows

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/fetch-tables")
def fetch_tables():
    return jsonify({"tables": get_tables()})

@app.route("/get-table-data")
def get_table_data_ajax():
    table_name = request.args.get("table")
    tables = get_tables()
    
    if table_name not in tables:  # Validate table exists
        return jsonify({"error": "Invalid table"}), 400
    
    columns, rows = get_table_data(table_name)
    return jsonify({
        "columns": columns,
        "rows": [list(row) for row in rows]  # Convert tuples to lists
    })

@app.route("/get-tables")
def get_tables():
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Query to get all tables from your schema
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'updated'
            AND table_type = 'BASE TABLE'
        """)
        
        tables = [row[0] for row in cur.fetchall()]
        
        cur.close()
        conn.close()
        
        return jsonify({"tables": tables})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get-columns")
def get_columns():
    try:
        table_name = request.args.get('table')
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Query to get column names for the selected table
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'updated' 
            AND table_name = %s
        """, (table_name,))
        
        columns = [row[0] for row in cur.fetchall()]
        
        cur.close()
        conn.close()
        
        return jsonify({"columns": columns})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Update the MAPS_DIR path
MAPS_DIR = os.path.join('static', 'maps')
os.makedirs(MAPS_DIR, exist_ok=True)

@app.route("/visualize")
def visualize():
    try:
        # Get parameters from request
        table_name = request.args.get("table")
        independent = request.args.get("independent")
        dependents = request.args.get("dependents").split(",")

        # Fetch data from database
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Select the columns chosen by user
        columns = [independent] + dependents
        query = f"SELECT {', '.join(columns)} FROM updated.{table_name}"
        cur.execute(query)
        data = cur.fetchall()
        
        # Convert to DataFrame and ensure numeric types
        df = pd.DataFrame(data, columns=columns)
        df = df.apply(pd.to_numeric, errors='coerce')  # Convert to numeric, replacing errors with NaN
        
        # Drop any rows with NaN values
        df = df.dropna()

        # Prepare dataset inputs
        g_y = df[independent].values.reshape((-1,1))  # Dependent variable
        g_X = df[dependents].values  # Independent variables

        # Get coordinates from Georgia example data
        georgia_data = pd.read_csv(ps.examples.get_path('GData_utm.csv'))
        u = georgia_data['X'].values
        v = georgia_data['Y'].values
        g_coords = list(zip(u,v))

        # Normalize variables
        g_X = (g_X - g_X.mean(axis=0)) / g_X.std(axis=0)
        g_y = (g_y - g_y.mean(axis=0)) / g_y.std(axis=0)

        # Generate map
        map_file = os.path.join(MAPS_DIR, f"{table_name}_{independent}_map.png")
        fig, ax = plt.subplots(figsize=(10,10))
        georgia_shp = gp.read_file(ps.examples.get_path('G_utm.shp'))
        georgia_shp.plot(ax=ax, edgecolor='black', facecolor='white')
        georgia_shp.centroid.plot(ax=ax, c='black')
        plt.savefig(map_file)
        plt.close()

        # Get GWR results
        gwr_selector = Sel_BW(g_coords, g_y, g_X)
        gwr_bw = gwr_selector.search(bw_min=2)
        gwr_results = GWR(g_coords, g_y, g_X, gwr_bw).fit()

        # Get MGWR results
        mgwr_selector = Sel_BW(g_coords, g_y, g_X, multi=True)
        mgwr_bw = mgwr_selector.search(multi_bw_min=[2])
        mgwr_results = MGWR(g_coords, g_y, g_X, mgwr_selector).fit()

        # Save GWR summary to a text file
        gwr_summary_filename = f"{table_name}_{independent}_gwr_summary.txt"
        gwr_summary_path = os.path.join(MAPS_DIR, gwr_summary_filename)

        # Save MGWR summary to a text file
        mgwr_summary_filename = f"{table_name}_{independent}_mgwr_summary.txt"
        mgwr_summary_path = os.path.join(MAPS_DIR, mgwr_summary_filename)

        # Get complete summary strings from the models
        try:
            # Redirect stdout to capture the full printed GWR summary
            import io
            import sys
            original_stdout = sys.stdout
            gwr_summary_io = io.StringIO()
            sys.stdout = gwr_summary_io
            gwr_results.summary()
            sys.stdout = original_stdout
            gwr_summary = gwr_summary_io.getvalue()
            
            # Redirect stdout to capture the full printed MGWR summary
            mgwr_summary_io = io.StringIO()
            sys.stdout = mgwr_summary_io
            mgwr_results.summary()
            sys.stdout = original_stdout
            mgwr_summary = mgwr_summary_io.getvalue()
        except:
            # Fallback if redirection doesn't work
            gwr_summary = str(gwr_results.summary())
            mgwr_summary = str(mgwr_results.summary())

        # Add dataset information to GWR summary
        gwr_content = f"""
Dataset: {table_name}
Dependent Variable: {independent}
Independent Variables: {', '.join(dependents)}
Number of Observations: {len(df)}

GWR MODEL RESULTS
=================
{gwr_summary}
"""

        # Add dataset information to MGWR summary
        mgwr_content = f"""
Dataset: {table_name}
Dependent Variable: {independent}
Independent Variables: {', '.join(dependents)}
Number of Observations: {len(df)}

MGWR MODEL RESULTS
=================
{mgwr_summary}
"""

        # Write to separate files
        with open(gwr_summary_path, 'w') as f:
            f.write(gwr_content)
        
        with open(mgwr_summary_path, 'w') as f:
            f.write(mgwr_content)

        # After creating the summary file, prepare GWR and MGWR results for mapping
        georgia_shp = gp.read_file(ps.examples.get_path('G_utm.shp'))
        
        # Add GWR parameters to GeoDataframe
        georgia_shp['gwr_intercept'] = gwr_results.params[:,0]
        for idx, col_name in enumerate(dependents, start=1):
            georgia_shp[f'gwr_{col_name}'] = gwr_results.params[:,idx]

        # Get filtered t-values for GWR
        gwr_filtered_t = gwr_results.filter_tvals()

        # Add MGWR parameters to GeoDataframe
        georgia_shp['mgwr_intercept'] = mgwr_results.params[:,0]
        for idx, col_name in enumerate(dependents, start=1):
            georgia_shp[f'mgwr_{col_name}'] = mgwr_results.params[:,idx]

        # Get filtered t-values for MGWR
        mgwr_filtered_t = mgwr_results.filter_tvals()

        # Generate comparison maps for each variable
        comparison_maps = []
        for idx, var_name in enumerate(['intercept'] + dependents):
            comparison_filename = f"{table_name}_{independent}_{var_name}_comparison_map.png"
            comparison_path = os.path.join(MAPS_DIR, comparison_filename)
            
            # Create comparison plots
            fig, axes = plt.subplots(nrows=1, ncols=2, figsize=(45,20))
            
            ax0 = axes[0]
            ax0.set_title(f'GWR {var_name.title()} Surface (BW: {str(gwr_bw)})', fontsize=40)
            ax1 = axes[1]
            ax1.set_title(f'MGWR {var_name.title()} Surface (BW: {str(mgwr_bw[idx])})', fontsize=40)

            # Find min and max values
            gwr_col = f'gwr_{var_name}'
            mgwr_col = f'mgwr_{var_name}'
            gwr_min = georgia_shp[gwr_col].min()
            gwr_max = georgia_shp[gwr_col].max()
            mgwr_min = georgia_shp[mgwr_col].min()
            mgwr_max = georgia_shp[mgwr_col].max()
            vmin = np.min([gwr_min, mgwr_min])
            vmax = np.max([gwr_max, mgwr_max])

            # Create a diverging colormap: red (negative) -> white (zero) -> blue (positive)
            colors = ['darkred', 'red', 'lightcoral', 'white', 'lightblue', 'blue', 'darkblue']
            cmap = mpl.colors.LinearSegmentedColormap.from_list("custom", colors, N=256)

            # If all values are on one side of zero, adjust the colormap
            if vmin >= 0:  # All positive values
                colors = ['white', 'lightblue', 'blue', 'darkblue']
                cmap = mpl.colors.LinearSegmentedColormap.from_list("custom", colors, N=256)
            elif vmax <= 0:  # All negative values
                colors = ['darkred', 'red', 'lightcoral', 'white']
                cmap = mpl.colors.LinearSegmentedColormap.from_list("custom", colors, N=256)

            # Create scalar mappable with the full range
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))

            # Plot GWR parameters
            georgia_shp.plot(gwr_col, cmap=cmap, ax=ax0, vmin=vmin, vmax=vmax, **{'edgecolor':'black', 'alpha':1.0})
            
            # Plot MGWR parameters
            georgia_shp.plot(mgwr_col, cmap=cmap, ax=ax1, vmin=vmin, vmax=vmax, **{'edgecolor':'black', 'alpha':1.0})

            # Set figure options
            fig.tight_layout()    
            fig.subplots_adjust(right=0.9)
            cax = fig.add_axes([0.92, 0.14, 0.03, 0.75])
            sm._A = []
            cbar = fig.colorbar(sm, cax=cax)
            cbar.ax.tick_params(labelsize=50) 
            ax0.get_xaxis().set_visible(False)
            ax0.get_yaxis().set_visible(False)
            ax1.get_xaxis().set_visible(False)
            ax1.get_yaxis().set_visible(False)

            # Save the comparison plot
            plt.savefig(comparison_path)
            plt.close()
            
            comparison_maps.append(f"/static/maps/{os.path.basename(comparison_path)}")

        # Update the return statement to include all maps
        return jsonify({
            "success": True,
            "bandwidth": float(gwr_bw),
            "mgwr_bandwidth": mgwr_bw.tolist(),
            "maps": [
                f"/static/maps/{os.path.basename(map_file)}",  # Original map
                *comparison_maps  # All comparison maps
            ],
            "gwr_summary_file": f"/static/maps/{gwr_summary_filename}",
            "mgwr_summary_file": f"/static/maps/{mgwr_summary_filename}",
            "gwr_results": {
                "params": gwr_results.params.tolist(),
                "bw": float(gwr_bw),
                "r2": float(gwr_results.R2)
            },
            "mgwr_results": {
                "params": mgwr_results.params.tolist(),
                "bw": mgwr_bw.tolist(),
                "r2": float(mgwr_results.R2)
            }
        })

    except Exception as e:
        print(f"Error in visualization: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/get-maps")
def get_maps():
    # List all map files in the maps directory
    map_files = [f"/static/maps/{file}" 
                 for file in os.listdir(MAPS_DIR) 
                 if file.endswith(".png")]
    return jsonify({"maps": map_files})

def truncate_colormap(cmap, minval=0.0, maxval=1.0, n=100):
    """Truncates a colormap between specified values."""
    new_cmap = mpl.colors.LinearSegmentedColormap.from_list(
        'trunc({n},{a:.2f},{b:.2f})'.format(n=cmap.name, a=minval, b=maxval),
        cmap(np.linspace(minval, maxval, n)))
    return new_cmap

def shift_colormap(cmap, start=0, midpoint=0.5, stop=1.0, name='shiftedcmap'):
    """Shifts the colormap to have the specified midpoint."""
    cdict = {
        'red': [],
        'green': [],
        'blue': [],
        'alpha': []
    }

    # Regular index to compute the colors
    reg_index = np.linspace(start, stop, 257)

    # Shifted index to match the data
    shift_index = np.hstack([
        np.linspace(0.0, midpoint, 128, endpoint=False), 
        np.linspace(midpoint, 1.0, 129, endpoint=True)
    ])

    for ri, si in zip(reg_index, shift_index):
        r, g, b, a = cmap(ri)

        cdict['red'].append((si, r, r))
        cdict['green'].append((si, g, g))
        cdict['blue'].append((si, b, b))
        cdict['alpha'].append((si, a, a))

    newcmap = mpl.colors.LinearSegmentedColormap(name, cdict)
    return newcmap

if __name__ == "__main__":
    app.run(debug=True)