"""Abstract Base Class for Quaternary Engine caching backends."""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class CacheBackend(ABC):
    """Abstract caching interface supporting deterministic query caching."""

    @staticmethod
    def _hash_key(endpoint: str, query_key: str) -> str:
        """Compute deterministic SHA-256 hash of endpoint and query key."""
        raw = f"{endpoint}:{query_key}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @abstractmethod
    def get(self, endpoint: str, query_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached response dict, or None on cache miss."""
        pass

    @abstractmethod
    def set(self, endpoint: str, query_key: str, data: Dict[str, Any]) -> None:
        """Store response dict in cache."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Purge all stored cache entries."""
        pass
