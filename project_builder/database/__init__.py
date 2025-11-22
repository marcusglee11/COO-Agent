import sqlite3

def verify_json1(conn: sqlite3.Connection) -> None:
    """
    Verifies that the SQLite connection has the JSON1 extension enabled.
    Raises RuntimeError if JSON1 is not available.
    """
    try:
        cursor = conn.execute("SELECT json_valid('[1]')")
        cursor.fetchone()
    except sqlite3.OperationalError:
        raise RuntimeError("SQLite JSON1 extension is not available.")
