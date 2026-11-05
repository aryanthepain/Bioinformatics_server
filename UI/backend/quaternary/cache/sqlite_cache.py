"""SQLite caching backend storing responses in a relational database table."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional

from quaternary.cache.base import CacheBackend


class SqliteCache(CacheBackend):
    """Relational SQLite cache backend."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS api_cache (
                    cache_key TEXT PRIMARY KEY,
                    endpoint TEXT NOT NULL,
                    query_key TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_endpoint ON api_cache (endpoint)")
            conn.commit()

    def get(self, endpoint: str, query_key: str) -> Optional[Dict[str, Any]]:
        cache_key = self._hash_key(endpoint, query_key)
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT response_json FROM api_cache WHERE cache_key = ?",
                    (cache_key,),
                )
                row = cursor.fetchone()
                if row:
                    return json.loads(row["response_json"])
                return None
        except Exception:
            return None

    def set(self, endpoint: str, query_key: str, data: Dict[str, Any]) -> None:
        cache_key = self._hash_key(endpoint, query_key)
        serialized = json.dumps(data)
        now = time.time()
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO api_cache (cache_key, endpoint, query_key, response_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        response_json = excluded.response_json,
                        created_at = excluded.created_at
                    """,
                    (cache_key, endpoint, query_key, serialized, now),
                )
                conn.commit()
        except Exception:
            pass

    def clear(self) -> None:
        """Purge all records from the cache table."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM api_cache")
                conn.commit()
        except Exception:
            pass
