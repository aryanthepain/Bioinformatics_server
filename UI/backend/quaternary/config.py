"""Hierarchical configuration for the Quaternary Structure Engine.

Supports resolution precedence:
1. Constructor keyword arguments (highest)
2. Local `quaternary_config.json` if present in current working directory
3. Environment variables (e.g. `QUATERNARY_CACHE_BACKEND`, `QUATERNARY_OFFLINE_MODE`)
4. Default field values (lowest)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field


class QuaternaryConfig(BaseModel):
    """Configuration model for caching, timeouts, retries, and execution modes."""

    cache_enabled: bool = True
    cache_backend: Literal["json", "sqlite"] = "json"
    cache_dir: Path = Path(".cache/quaternary")
    sqlite_db_path: Path = Path(".cache/quaternary.db")
    timeout: float = 30.0
    max_retries: int = 3
    backoff_factor: float = 1.0
    offline_mode: bool = False
    force_refresh: bool = False
    biogrid_api_key: Optional[str] = None

    def __init__(self, **data: Any) -> None:
        merged_data: Dict[str, Any] = {}

        # 1. Environment variables
        env_mappings = {
            "QUATERNARY_CACHE_ENABLED": ("cache_enabled", lambda v: v.lower() in ("true", "1", "yes")),
            "QUATERNARY_CACHE_BACKEND": ("cache_backend", lambda v: v),
            "QUATERNARY_CACHE_DIR": ("cache_dir", lambda v: Path(v)),
            "QUATERNARY_SQLITE_DB_PATH": ("sqlite_db_path", lambda v: Path(v)),
            "QUATERNARY_TIMEOUT": ("timeout", lambda v: float(v)),
            "QUATERNARY_MAX_RETRIES": ("max_retries", lambda v: int(v)),
            "QUATERNARY_BACKOFF_FACTOR": ("backoff_factor", lambda v: float(v)),
            "QUATERNARY_OFFLINE_MODE": ("offline_mode", lambda v: v.lower() in ("true", "1", "yes")),
            "QUATERNARY_FORCE_REFRESH": ("force_refresh", lambda v: v.lower() in ("true", "1", "yes")),
            "BIOGRID_API_KEY": ("biogrid_api_key", lambda v: v),
        }

        for env_var, (field_name, parser) in env_mappings.items():
            if env_var in os.environ:
                try:
                    merged_data[field_name] = parser(os.environ[env_var])
                except Exception:
                    pass

        # 2. Local config file quaternary_config.json if present
        local_cfg = Path("quaternary_config.json")
        if local_cfg.is_file():
            try:
                with open(local_cfg, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                    if isinstance(file_data, dict):
                        for k, v in file_data.items():
                            if k in ("cache_dir", "sqlite_db_path") and v is not None:
                                merged_data[k] = Path(v)
                            else:
                                merged_data[k] = v
            except Exception:
                pass

        # 3. Explicit kwargs passed to constructor
        for k, v in data.items():
            if v is not None:
                if k in ("cache_dir", "sqlite_db_path") and isinstance(v, str):
                    merged_data[k] = Path(v)
                else:
                    merged_data[k] = v
            else:
                merged_data[k] = v

        super().__init__(**merged_data)
