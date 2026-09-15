import os
import psycopg2
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(".env.local")

DB_URL = os.getenv("SUPABASE_DB_URL")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBEDDING_MODEL = "text-embedding-3-small"

def search_menu(query, top_k=3):
    # Convert the question into an embedding
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=query)
    query_vector = response.data[0].embedding

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Find the closest matching menu items (cosine distance - smaller = more similar)
    cur.execute(
        """
        SELECT name, price, description, 1 - (embedding <=> %s::vector) AS similarity
        FROM menu_items
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """,
        (query_vector, query_vector, top_k),
    )
    results = cur.fetchall()
    cur.close()
    conn.close()
    return results

# Test it
query = "something spicy"
print(f"Searching for: '{query}'\n")
for name, price, desc, similarity in search_menu(query):
    print(f"{name} (${price}) - {desc}  [similarity: {similarity:.3f}]")