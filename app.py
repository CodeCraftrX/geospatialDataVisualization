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

app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    "dbname": "geoda_db",
    "user": "geoda_user",
    "password": "Atlanta123!",
    "host": "pgsql.dataconn.net",
    "port": "5432"
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

# Define maps directory
MAPS_DIR = 'maps'
os.makedirs(MAPS_DIR, exist_ok=True)

@app.route("/visualize")
def visualize():
    # Get parameters from query string
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

    try:
        # Calibrate GWR model
        gwr_selector = Sel_BW(g_coords, g_y, g_X)
        gwr_bw = gwr_selector.search(bw_min=2)
        gwr_results = GWR(g_coords, g_y, g_X, gwr_bw).fit()
        
        # Generate and save map
        map_file = os.path.join(MAPS_DIR, f"{table_name}_{independent}_map.png")
        fig, ax = plt.subplots(figsize=(10,10))
        georgia_shp = gp.read_file(ps.examples.get_path('G_utm.shp'))
        georgia_shp.plot(ax=ax, edgecolor='black', facecolor='white')
        georgia_shp.centroid.plot(ax=ax, c='black')
        plt.savefig(map_file)
        plt.close()

        return jsonify({
            "success": True,
            "bandwidth": float(gwr_bw),
            "maps": [f"/maps/{os.path.basename(map_file)}"]
        })

    except Exception as e:
        print(f"Error in GWR analysis: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route("/get-maps")
def get_maps():
    # List all map files in the maps directory
    map_files = [f"/maps/{file}" 
                 for file in os.listdir(MAPS_DIR) 
                 if file.endswith(".png")]
    return jsonify({"maps": map_files})

if __name__ == "__main__":
    app.run(debug=True)