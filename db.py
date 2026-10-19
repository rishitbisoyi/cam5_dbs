import mysql.connector
from mysql.connector import errorcode
from contextlib import contextmanager
from config import Config

def get_db_connection():
    """Create and return a new MySQL connection using environment configuration."""
    cfg = Config.get_db_config()
    return mysql.connector.connect(**cfg)

@contextmanager
def get_db_cursor(commit=False, dictionary=True):
    """
    Context manager that yields a cursor and safely handles commit, rollback, and cleanup.
    Usage:
        with get_db_cursor(commit=True) as (conn, cursor):
            cursor.execute(...)
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=dictionary)
    try:
        yield conn, cursor
        if commit:
            conn.commit()
    except Exception as e:
        if conn.is_connected():
            conn.rollback()
        raise e
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

def query_db(query, args=(), one=False, dictionary=True):
    """Execute a read query and return records safely."""
    with get_db_cursor(commit=False, dictionary=dictionary) as (conn, cursor):
        cursor.execute(query, args)
        rows = cursor.fetchall()
        return (rows[0] if rows else None) if one else rows

def execute_db(query, args=(), commit=True):
    """Execute an insert/update/delete query and return lastrowid and rowcount."""
    with get_db_cursor(commit=commit, dictionary=True) as (conn, cursor):
        cursor.execute(query, args)
        last_id = cursor.lastrowid
        affected = cursor.rowcount
        return {"last_id": last_id, "rowcount": affected}
