"""Pluggable caching backends for the Quaternary Structure Engine."""

from __future__ import annotations

from typing import Optional

from quaternary.cache.base import CacheBackend
from quaternary.cache.json_cache import JsonDirectoryCache
from quaternary.cache.sqlite_cache import SqliteCache
from quaternary.config import QuaternaryConfig


def get_cache_backend(config: QuaternaryConfig) -> Optional[CacheBackend]:
    """Factory creating the configured CacheBackend instance or None if disabled."""
    if not config.cache_enabled:
        return None

    if config.cache_backend == "sqlite":
        return SqliteCache(config.sqlite_db_path)
    return JsonDirectoryCache(config.cache_dir)


__all__ = [
    "CacheBackend",
    "JsonDirectoryCache",
    "SqliteCache",
    "get_cache_backend",
]
