import psycopg2

# Database connection details
DB_CONFIG = {
    "dbname": "geoda_db",
    "user": "geoda_user",
    "password": "Atlanta123!",
    "host": "pgsql.dataconn.net",  # Change if running remotely
    "port": "5432"  # Default PostgreSQL port
}

def get_tables():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()
    cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'updated';")  # Updated schema name
    tables = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return tables

def fetch_table_data():
    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Fetch column names
    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'updated' AND table_name = 'oxaaca';")
    columns = [row[0] for row in cursor.fetchall()]
    print(f"Columns: {columns}")

    # Fetch first 10 rows
    #cursor.execute("SELECT * FROM updated.oxaaca LIMIT 2;")  # Using schema.table notation
    rows = cursor.fetchall()
    
    #print(f"First 10 Rows: {rows}")
    
    cursor.close()
    conn.close()

tables = get_tables()
print(f"Available Tables: {tables}")

if tables:
    print(f"\nFetching data from table: updated.oxaaca")
    fetch_table_data()