"""JSON directory caching backend storing responses as discrete JSON files."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Optional

from quaternary.cache.base import CacheBackend


class JsonDirectoryCache(CacheBackend):
    """File-system JSON directory cache implementation."""

    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, endpoint: str, query_key: str) -> Path:
        sanitized_endpoint = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in endpoint)
        endpoint_dir = self.cache_dir / sanitized_endpoint
        endpoint_dir.mkdir(parents=True, exist_ok=True)
        key_hash = self._hash_key(endpoint, query_key)
        return endpoint_dir / f"{key_hash}.json"

    def get(self, endpoint: str, query_key: str) -> Optional[Dict[str, Any]]:
        path = self._get_file_path(endpoint, query_key)
        if not path.is_file():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def set(self, endpoint: str, query_key: str, data: Dict[str, Any]) -> None:
        path = self._get_file_path(endpoint, query_key)
        tmp_path = path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            tmp_path.replace(path)
        except Exception:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    def clear(self) -> None:
        """Purge the cache directory."""
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir, ignore_errors=True)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
