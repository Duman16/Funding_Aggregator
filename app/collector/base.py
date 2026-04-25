import asyncio
import random
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from fake_useragent import UserAgent
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings

logger = structlog.get_logger()
ua = UserAgent()


class BaseCollector(ABC):
    """Abstract base class for all data collectors."""

    source_name: str = "base"

    def __init__(self):
        self.client: httpx.AsyncClient | None = None
        self.stats = {
            "collected": 0,
            "new": 0,
            "updated": 0,
            "errors": 0,
            "started_at": None,
        }

    def _get_headers(self) -> dict[str, str]:
        return {
            "User-Agent": ua.random,
            "Accept": "application/json, text/html,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    async def _random_delay(self):
        delay = random.uniform(settings.COLLECTOR_DELAY_MIN, settings.COLLECTOR_DELAY_MAX)
        await asyncio.sleep(delay)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def _fetch(self, url: str, **kwargs) -> httpx.Response:
        await self._random_delay()
        headers = self._get_headers()
        headers.update(kwargs.pop("headers", {}))
        response = await self.client.get(url, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        return response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def _post(self, url: str, **kwargs) -> httpx.Response:
        await self._random_delay()
        headers = self._get_headers()
        headers.update(kwargs.pop("headers", {}))
        response = await self.client.post(url, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        return response

    @abstractmethod
    async def collect(self) -> list[dict[str, Any]]:
        """Collect raw data and return list of grant dicts."""
        pass

    async def run(self) -> dict[str, Any]:
        self.stats["started_at"] = datetime.now(UTC)
        log = logger.bind(source=self.source_name)

        async with httpx.AsyncClient(follow_redirects=True) as client:
            self.client = client
            try:
                log.info("collector.started")
                data = await self.collect()
                self.stats["collected"] = len(data)
                log.info("collector.finished", collected=len(data))
                return {"status": "success", "data": data, "stats": self.stats}
            except Exception as e:
                self.stats["errors"] += 1
                log.error("collector.error", error=str(e))
                return {"status": "failed", "data": [], "stats": self.stats, "error": str(e)}
            finally:
                self.client = None
