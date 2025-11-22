import sqlite3
import os

def apply_schema(conn: sqlite3.Connection) -> None:
    """
    Applies the schema.sql to the provided SQLite connection.
    """
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    
    conn.executescript(schema_sql)
    conn.commit()

def init_db(db_path: str) -> None:
    """
    Initializes the database at the given path with the schema.
    """
    conn = sqlite3.connect(db_path)
    try:
        apply_schema(conn)
    finally:
        conn.close()
