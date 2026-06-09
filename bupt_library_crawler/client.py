from __future__ import annotations

import logging
import random
import time
from typing import Any

import requests


LOGGER = logging.getLogger(__name__)


class OpacClient:
    def __init__(
        self,
        base_url: str = "http://opac.bupt.edu.cn:8080",
        delay: float = 1.0,
        timeout: float = 30.0,
        retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; bupt-library-crawler/0.1; educational research)",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )

    def _sleep(self) -> None:
        jitter = random.uniform(0, self.delay * 0.25) if self.delay > 0 else 0
        time.sleep(self.delay + jitter)

    def get_text(self, path: str, referer: str | None = None) -> str:
        return self._request("GET", path, referer=referer).text

    def post_json(self, path: str, data: dict[str, Any], referer: str) -> dict[str, Any]:
        response = self._request("POST", path, data=data, referer=referer)
        return response.json()

    def _request(
        self,
        method: str,
        path: str,
        data: dict[str, Any] | None = None,
        referer: str | None = None,
    ) -> requests.Response:
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        headers = {"Referer": referer or f"{self.base_url}/index.html"}
        last_error: Exception | None = None

        for attempt in range(1, self.retries + 1):
            self._sleep()
            try:
                response = self.session.request(
                    method,
                    url,
                    data=data,
                    headers=headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                if "Error Referer" in response.text:
                    raise RuntimeError("OPAC rejected the request because Referer is missing or invalid.")
                return response
            except Exception as exc:  # noqa: BLE001 - retry boundary
                last_error = exc
                wait = min(30.0, self.delay * (2 ** attempt))
                LOGGER.warning("request failed (%s %s), attempt %s/%s: %s", method, url, attempt, self.retries, exc)
                time.sleep(wait)

        raise RuntimeError(f"request failed after {self.retries} attempts: {url}") from last_error

