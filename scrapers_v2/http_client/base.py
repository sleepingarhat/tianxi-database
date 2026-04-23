"""Async HTTP client for HKJC with retry, throttle, and UA spoof."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .throttle import TokenBucket

logger = logging.getLogger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
}

# Retryable errors (transient network / server issues)
_RETRYABLE = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
    httpx.ReadError,
)


class AsyncHKJCClient:
    """Async HTTP client wrapping httpx.AsyncClient with HKJC-specific defaults.

    - Token bucket rate limit (default 10 req/s)
    - Exponential backoff retry on transient errors
    - Follows redirects (HKJC auto-redirects old .aspx to /zh-hk/)
    - HTTP/2 enabled
    """

    def __init__(
        self,
        *,
        rate: float = 10.0,
        timeout: float = 30.0,
        max_retries: int = 3,
        headers: dict[str, str] | None = None,
        concurrency: int = 10,
    ) -> None:
        self._bucket = TokenBucket(rate=rate, capacity=max(rate, 5.0))
        self._sem = asyncio.Semaphore(concurrency)
        self._client = httpx.AsyncClient(
            http2=True,
            timeout=timeout,
            follow_redirects=True,
            headers={**DEFAULT_HEADERS, **(headers or {})},
            # HKJC sometimes rejects without Referer on deep links
            limits=httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=concurrency),
        )
        self._max_retries = max_retries

    async def __aenter__(self) -> AsyncHKJCClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    async def get(
        self, url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None
    ) -> httpx.Response:
        """GET with retry, throttle, and concurrency gate. Returns final Response."""
        await self._bucket.acquire()
        async with self._sem:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self._max_retries),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                retry=retry_if_exception_type(_RETRYABLE),
                reraise=True,
            ):
                with attempt:
                    resp = await self._client.get(url, params=params, headers=headers)
                    # HKJC returns 200 with error page sometimes; raise on 5xx
                    if resp.status_code >= 500:
                        raise httpx.RemoteProtocolError(f"HTTP {resp.status_code}", request=resp.request)
                    return resp

    async def get_text(self, url: str, **kwargs: Any) -> str:
        resp = await self.get(url, **kwargs)
        resp.raise_for_status()
        return resp.text

    async def post(
        self, url: str, *, json: dict[str, Any] | None = None, data: dict[str, Any] | None = None
    ) -> httpx.Response:
        await self._bucket.acquire()
        async with self._sem:
            resp = await self._client.post(url, json=json, data=data)
            return resp


def build_client(
    *, rate: float = 10.0, concurrency: int = 10, timeout: float = 30.0
) -> AsyncHKJCClient:
    """Factory for a ready-to-use async client."""
    return AsyncHKJCClient(rate=rate, concurrency=concurrency, timeout=timeout)
