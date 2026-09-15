import os
import json
import psycopg2
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(".env.local")

DB_URL = os.getenv("SUPABASE_DB_URL")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

EMBEDDING_MODEL = "text-embedding-3-small"  # 1536 dimensions

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# 1. Create the table (if it doesn't exist yet)
cur.execute("""
    CREATE TABLE IF NOT EXISTS menu_items (
        id SERIAL PRIMARY KEY,
        cuisine TEXT,
        category TEXT,
        name TEXT NOT NULL,
        price NUMERIC,
        description TEXT,
        content TEXT,
        embedding VECTOR(1536)
    );
""")
conn.commit()
print("Table 'menu_items' ready.")

# 2. Clear old data (so re-running this script doesn't duplicate items)
cur.execute("DELETE FROM menu_items;")
conn.commit()

# 3. Load the menu
with open("menu.json", "r", encoding="utf-8") as f:
    menu = json.load(f)

def embed(text):
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
    return response.data[0].embedding

count = 0

def insert_item(cuisine, category, item):
    global count
    content = f"{item['name']} ({category}, {cuisine}): {item['desc']} - ${item['price']}"
    vector = embed(content)
    cur.execute(
        """
        INSERT INTO menu_items (cuisine, category, name, price, description, content, embedding)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (cuisine, category, item["name"], item["price"], item["desc"], content, vector),
    )
    count += 1
    print(f"Inserted: {item['name']}")

for cuisine, categories in menu.items():
    if cuisine == "beverages":
        for item in categories:
            insert_item("beverages", "Beverages & Desserts", item)
    else:
        for category, items in categories.items():
            for item in items:
                insert_item(cuisine, category, item)

conn.commit()

# 4. Create a vector similarity index for fast search
cur.execute("""
    CREATE INDEX IF NOT EXISTS menu_items_embedding_idx
    ON menu_items USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);
""")
conn.commit()

print(f"\nDone. Inserted {count} menu items with embeddings into Supabase.")

cur.close()
conn.close()