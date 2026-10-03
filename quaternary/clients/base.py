"""Base BioServices/REST client adapter with retries, caching, and HTTP 303 interception."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from quaternary.cache.base import CacheBackend
from quaternary.config import QuaternaryConfig

logger = logging.getLogger(__name__)


class BaseBioClient:
    """Standardized biological API client providing retries, caching, and async job polling."""

    def __init__(
        self,
        config: QuaternaryConfig,
        cache: Optional[CacheBackend] = None,
    ) -> None:
        self.config = config
        self.cache = cache
        self.fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create and configure a requests.Session with urllib3 exponential backoff retries."""
        session = requests.Session()
        retries = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.backoff_factor,
            status_forcelist=[429, 502, 503, 504],
            raise_on_status=False,
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def get_with_cache(
        self,
        endpoint: str,
        query_key: str,
        fetch_fn: Callable[[], Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Wrap an API fetch call with cache inspection and storage."""
        # 1. Offline fixture mode
        if self.config.offline_mode:
            fixture = self.load_fixture(endpoint, query_key)
            if fixture is not None:
                return fixture

        # 2. Check cache unless force_refresh is True
        if self.cache is not None and not self.config.force_refresh:
            cached = self.cache.get(endpoint, query_key)
            if cached is not None:
                return cached

        # 3. Live fetch
        data = fetch_fn()

        # 4. Save to cache
        if self.cache is not None and data is not None:
            self.cache.set(endpoint, query_key, data)

        return data

    def load_fixture(self, endpoint: str, query_key: str) -> Optional[Dict[str, Any]]:
        """Load bundled JSON fixture for offline testing."""
        if not self.fixtures_dir.exists():
            return None

        # Look for endpoint-specific fixture file e.g. uniprot_sample.json
        candidate_names = [
            f"{endpoint}_{query_key}.json",
            f"{endpoint}_sample.json",
            f"{endpoint}.json",
        ]
        for name in candidate_names:
            file_path = self.fixtures_dir / name
            if file_path.is_file():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to read fixture {file_path}: {e}")

        return None

    def poll_async_job(
        self,
        status_url: str,
        timeout_sec: Optional[int] = None,
        poll_interval: float = 2.0,
    ) -> Dict[str, Any]:
        """Poll an async job endpoint with strict HTTP 303 redirect interception (enforcing D-11).

        Specifically uses allow_redirects=False to catch HTTP 303 See Other status codes,
        extracting the Location header to retrieve completed job results.
        """
        max_timeout = float(timeout_sec) if timeout_sec is not None else float(self.config.timeout * 4)
        start_time = time.time()
        current_interval = poll_interval

        while True:
            elapsed = time.time() - start_time
            if elapsed > max_timeout:
                raise TimeoutError(f"Async job at {status_url} timed out after {elapsed:.1f} seconds")

            resp = self.session.get(
                status_url,
                allow_redirects=False,
                timeout=self.config.timeout,
            )

            # Explicit HTTP 303 Redirect Interception (resolving Roadblock 2)
            if resp.status_code == 303:
                location = resp.headers.get("Location")
                if not location:
                    raise RuntimeError(f"HTTP 303 received from {status_url} but Location header was missing")
                result_resp = self.session.get(location, timeout=self.config.timeout)
                result_resp.raise_for_status()
                return result_resp.json()

            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    data = {"text": resp.text}

                job_status = (
                    data.get("jobStatus")
                    or data.get("status")
                    or ("FINISHED" if "results" in data else None)
                )
                if job_status in ("FINISHED", "SUCCESS", "COMPLETED"):
                    return data
                elif job_status in ("FAILED", "ERROR"):
                    raise RuntimeError(f"Async job failed with status {job_status}: {data}")

            # Backoff before next polling attempt
            time.sleep(current_interval)
            current_interval = min(current_interval * 1.5, 15.0)
