import pandas as pd
import geopandas as gpd
import libpysal as ps
from sqlalchemy import create_engine
from geoalchemy2 import Geometry

# Database credentials (Modify these as needed)
DB_USER = "geoda_user"
DB_PASSWORD = "Atlanta123!"
DB_NAME = "geoda_db"
DB_HOST = "pgsql.dataconn.net"  # Use 'localhost' if running locally
DB_PORT = "5432"  # Default PostgreSQL port is 5432

# Create database connection
engine = create_engine(f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}')

# Fetch and load CSV data
csv_path = ps.examples.get_path('GData_utm.csv')
georgia_data = pd.read_csv(csv_path)

table_name_csv = "georgia_data_table"
georgia_data.to_sql(table_name_csv, engine, if_exists='replace', index=False)
print(f"CSV data successfully inserted into table: {table_name_csv}")

# Fetch and load shapefile data
shp_path = ps.examples.get_path('G_utm.shp')
georgia_shp = gpd.read_file(shp_path)

table_name_shp = "georgia_shapefile"
georgia_shp.to_postgis(table_name_shp, engine, if_exists='replace', index=False)
print(f"Shapefile successfully inserted into table: {table_name_shp}")
