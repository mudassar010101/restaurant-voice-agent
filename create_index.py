import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(".env.local")
DB_URL = os.getenv("SUPABASE_DB_URL")

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

cur.execute("""
    CREATE INDEX IF NOT EXISTS menu_items_embedding_idx
    ON menu_items USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 2);
""")
conn.commit()

print("Index created successfully.")

cur.close()
conn.close()