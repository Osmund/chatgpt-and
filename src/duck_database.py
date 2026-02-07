"""
Sentralisert DatabaseManager for anda.

Gir thread-safe tilgang til SQLite via threading.local() connections.
Hver thread får sin egen connection som gjenbrukes.

Bruk:
    from src.duck_database import get_db

    # Context manager med auto-commit/rollback:
    with get_db().cursor() as c:
        c.execute("SELECT * FROM ...")
        rows = c.fetchall()

    # Rå connection (for spesielle tilfeller):
    conn = get_db().connection()
"""

import sqlite3
import threading
from contextlib import contextmanager

from src.duck_config import DB_PATH


class DatabaseManager:
    """
    Thread-safe SQLite connection manager med connection-per-thread.
    Singleton — bruk get_db() for å hente instansen.
    """
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._local = threading.local()
    
    @classmethod
    def get_instance(cls, db_path: str = None) -> 'DatabaseManager':
        """Hent singleton-instansen."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db_path)
        return cls._instance
    
    def connection(self) -> sqlite3.Connection:
        """
        Hent thread-local connection. Opprettes ved første bruk per thread.
        Connection gjenbrukes for alle påfølgende kall i samme thread.
        """
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn = conn
        return conn
    
    @contextmanager
    def cursor(self):
        """
        Context manager som gir en cursor med auto-commit/rollback.
        
        Bruk:
            with db.cursor() as c:
                c.execute("INSERT INTO ...", (...))
                # commit skjer automatisk
        """
        conn = self.connection()
        c = conn.cursor()
        try:
            yield c
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    def close_thread_connection(self):
        """Lukk connection for nåværende thread (f.eks. ved thread exit)."""
        conn = getattr(self._local, 'conn', None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None


def get_db(db_path: str = None) -> DatabaseManager:
    """Hent singleton DatabaseManager-instansen."""
    return DatabaseManager.get_instance(db_path)
