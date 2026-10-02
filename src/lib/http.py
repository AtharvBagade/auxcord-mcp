"""HTTP Client wrapper library on top of httpx.

Exposes managed HTTP clients (both async and sync) with connection pooling,
configurable timeouts, default headers, and singleton management for tools
and scripts across the service.
"""

import json
from typing import Any, Self

import httpx

from src.lib.logger import logger


class HTTPClientError(Exception):
    """Base exception class for HTTP client library errors."""



# Re-export key httpx exceptions for unified error handling
HTTPStatusError = httpx.HTTPStatusError
RequestError = httpx.RequestError
TimeoutException = httpx.TimeoutException
NetworkError = httpx.NetworkError


class HTTPClient:
    """Async HTTP Client wrapper built on top of httpx.AsyncClient."""

    def __init__(
        self,
        base_url: str = "",
        headers: dict[str, str] | None = None,
        timeout: float | httpx.Timeout = 10.0,
        limits: httpx.Limits | None = None,
        follow_redirects: bool = True,
        client: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url
        self._custom_client = client
        if client is not None:
            self._client = client
        else:
            self._client = httpx.AsyncClient(
                base_url=base_url,
                headers=headers,
                timeout=timeout,
                limits=limits
                or httpx.Limits(max_keepalive_connections=20, max_connections=100),
                follow_redirects=follow_redirects,
            )

    @property
    def is_closed(self) -> bool:
        """Check if underlying client is closed."""
        return self._client.is_closed

    async def close(self) -> None:
        """Close the underlying async HTTP client."""
        if not self._client.is_closed:
            await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        files: Any | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute an async HTTP request."""
        return await self._client.request(
            method=method.upper(),
            url=url,
            params=params,
            headers=headers,
            json=json,
            data=data,
            files=files,
            timeout=timeout,
            **kwargs,
        )

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Execute async GET request."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Execute async POST request."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        """Execute async PUT request."""
        return await self.request("PUT", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        """Execute async PATCH request."""
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """Execute async DELETE request."""
        return await self.request("DELETE", url, **kwargs)

    async def head(self, url: str, **kwargs: Any) -> httpx.Response:
        """Execute async HEAD request."""
        return await self.request("HEAD", url, **kwargs)

    async def options(self, url: str, **kwargs: Any) -> httpx.Response:
        """Execute async OPTIONS request."""
        return await self.request("OPTIONS", url, **kwargs)

    async def request_json(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Any:
        """Execute request and parse JSON response, raising for HTTP status errors."""
        response = await self.request(method, url, **kwargs)
        response.raise_for_status()
        if response.status_code in (202, 204) or not len(response.text):
            return {}
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            logger.error("JSON parse error from Spotify API: %s", exc)
            raise ValueError("Invalid JSON response from Spotify API")


class SyncHTTPClient:
    """Synchronous HTTP Client wrapper built on top of httpx.Client."""

    def __init__(
        self,
        base_url: str = "",
        headers: dict[str, str] | None = None,
        timeout: float | httpx.Timeout = 10.0,
        limits: httpx.Limits | None = None,
        follow_redirects: bool = True,
        client: httpx.Client | None = None,
    ):
        self.base_url = base_url
        if client is not None:
            self._client = client
        else:
            self._client = httpx.Client(
                base_url=base_url,
                headers=headers,
                timeout=timeout,
                limits=limits
                or httpx.Limits(max_keepalive_connections=20, max_connections=100),
                follow_redirects=follow_redirects,
            )

    @property
    def is_closed(self) -> bool:
        """Check if underlying client is closed."""
        return self._client.is_closed

    def close(self) -> None:
        """Close the underlying sync HTTP client."""
        if not self._client.is_closed:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json: Any | None = None,
        data: Any | None = None,
        files: Any | None = None,
        timeout: float | httpx.Timeout | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Execute a sync HTTP request."""
        return self._client.request(
            method=method.upper(),
            url=url,
            params=params,
            headers=headers,
            json=json,
            data=data,
            files=files,
            timeout=timeout,
            **kwargs,
        )

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Execute sync GET request."""
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Execute sync POST request."""
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs: Any) -> httpx.Response:
        """Execute sync PUT request."""
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs: Any) -> httpx.Response:
        """Execute sync PATCH request."""
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """Execute sync DELETE request."""
        return self.request("DELETE", url, **kwargs)

    def head(self, url: str, **kwargs: Any) -> httpx.Response:
        """Execute sync HEAD request."""
        return self.request("HEAD", url, **kwargs)

    def options(self, url: str, **kwargs: Any) -> httpx.Response:
        """Execute sync OPTIONS request."""
        return self.request("OPTIONS", url, **kwargs)

    def request_json(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Any:
        """Execute sync request and parse JSON response, raising for HTTP status errors."""
        response = self.request(method, url, **kwargs)
        response.raise_for_status()
        if response.status_code in (202, 204) or not len(response.text):
            return {}
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            logger.error("JSON parse error from Spotify API: %s", exc)
            raise ValueError("Invalid JSON response from Spotify API")


# Singletons / Global Managed Instances
_async_http_client: HTTPClient | None = None
_sync_http_client: SyncHTTPClient | None = None


def get_http_client(
    base_url: str = "",
    headers: dict[str, str] | None = None,
    force_new: bool = False,
) -> HTTPClient:
    """Get or create singleton Async HTTPClient instance."""
    global _async_http_client
    if force_new or _async_http_client is None or _async_http_client.is_closed:
        _async_http_client = HTTPClient(base_url=base_url, headers=headers)
    return _async_http_client


def get_sync_http_client(
    base_url: str = "",
    headers: dict[str, str] | None = None,
    force_new: bool = False,
) -> SyncHTTPClient:
    """Get or create singleton Sync HTTPClient instance."""
    global _sync_http_client
    if force_new or _sync_http_client is None or _sync_http_client.is_closed:
        _sync_http_client = SyncHTTPClient(base_url=base_url, headers=headers)
    return _sync_http_client


async def close_http_clients() -> None:
    """Close global async and sync HTTP clients."""
    global _async_http_client, _sync_http_client
    if _async_http_client is not None and not _async_http_client.is_closed:
        await _async_http_client.close()
        _async_http_client = None

    if _sync_http_client is not None and not _sync_http_client.is_closed:
        _sync_http_client.close()
        _sync_http_client = None
