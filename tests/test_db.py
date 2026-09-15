import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(".env.local")

conn_string = os.getenv("SUPABASE_DB_URL")

if not conn_string:
    raise ValueError("SUPABASE_DB_URL not found in .env.local")

try:
    conn = psycopg2.connect(conn_string)
    cur = conn.cursor()
    cur.execute("SELECT version();")
    version = cur.fetchone()
    print("Connected successfully!")
    print("Postgres version:", version[0])

    # Check if the vector extension is enabled
    cur.execute("SELECT * FROM pg_extension WHERE extname = 'vector';")
    result = cur.fetchone()
    if result:
        print("PGVector extension is enabled.")
    else:
        print("WARNING: PGVector extension NOT found.")

    cur.close()
    conn.close()

except Exception as e:
    print("Connection failed:", e)