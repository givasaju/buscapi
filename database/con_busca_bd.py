import psycopg2

conn = psycopg2.connect(
    dbname="buscapi_bd",
    user="postgres",
    password="givas2025",
    host="localhost",    # ou IP do servidor PostgreSQL
    port=5432            # padrão postgres
)
#cursor = conn.cursor()
#def fetch_data(query, params=None):
#    cursor.execute(query, params)
#    return cursor.fetchall()
