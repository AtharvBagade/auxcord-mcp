"""Unit tests for the HTTP client wrapper library (src/lib/http.py)."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.lib.http import (
    HTTPClient,
    HTTPClientError,
    HTTPStatusError,
    NetworkError,
    RequestError,
    SyncHTTPClient,
    TimeoutException,
    close_http_clients,
    get_http_client,
    get_sync_http_client,
)


@pytest.mark.asyncio
async def test_async_http_client_request_methods():
    """Test HTTPClient async request methods."""
    mock_httpx = AsyncMock(spec=httpx.AsyncClient)
    mock_httpx.is_closed = False
    mock_httpx.aclose = AsyncMock()

    mock_httpx.request.return_value = httpx.Response(
        200, json={"key": "value"}, request=httpx.Request("GET", "https://api.example.com/json-endpoint")
    )

    client = HTTPClient(base_url="https://api.example.com", client=mock_httpx)

    res_get = await client.get("/test")
    assert res_get.status_code == 200
    mock_httpx.request.assert_called_with(
        method="GET",
        url="/test",
        params=None,
        headers=None,
        json=None,
        data=None,
        files=None,
        timeout=None,
    )

    res_post = await client.post("/items", json={"name": "test"})
    assert res_post.status_code == 200

    res_json = await client.request_json("GET", "/json-endpoint")
    assert res_json == {"key": "value"}

    await client.close()
    mock_httpx.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_async_http_client_context_manager():
    """Test HTTPClient async context manager."""
    mock_httpx = AsyncMock(spec=httpx.AsyncClient)
    mock_httpx.is_closed = False
    mock_httpx.aclose = AsyncMock()

    async with HTTPClient(client=mock_httpx) as client:
        assert not client.is_closed

    mock_httpx.aclose.assert_called_once()


def test_sync_http_client_request_methods():
    """Test SyncHTTPClient sync request methods."""
    mock_httpx = MagicMock(spec=httpx.Client)
    mock_httpx.is_closed = False

    mock_httpx.request.return_value = httpx.Response(
        200, json={"sync": "ok"}, request=httpx.Request("POST", "https://api.example.com/sync-json")
    )

    client = SyncHTTPClient(base_url="https://api.example.com", client=mock_httpx)

    res_get = client.get("/test-sync")
    assert res_get.status_code == 200
    mock_httpx.request.assert_called_with(
        method="GET",
        url="/test-sync",
        params=None,
        headers=None,
        json=None,
        data=None,
        files=None,
        timeout=None,
    )

    res_json = client.request_json("POST", "/sync-json", json={"foo": "bar"})
    assert res_json == {"sync": "ok"}

    client.close()
    mock_httpx.close.assert_called_once()


def test_sync_http_client_context_manager():
    """Test SyncHTTPClient context manager."""
    mock_httpx = MagicMock(spec=httpx.Client)
    mock_httpx.is_closed = False

    with SyncHTTPClient(client=mock_httpx) as client:
        assert not client.is_closed

    mock_httpx.close.assert_called_once()


@pytest.mark.asyncio
async def test_singleton_getters_and_close_all():
    """Test get_http_client, get_sync_http_client, and close_http_clients."""
    async_client1 = get_http_client()
    async_client2 = get_http_client()
    assert async_client1 is async_client2

    sync_client1 = get_sync_http_client()
    sync_client2 = get_sync_http_client()
    assert sync_client1 is sync_client2

    await close_http_clients()

    assert async_client1.is_closed
    assert sync_client1.is_closed


def test_exception_reexports():
    """Verify exception classes are re-exported correctly."""
    assert issubclass(HTTPClientError, Exception)
    assert issubclass(HTTPStatusError, httpx.HTTPStatusError)
    assert issubclass(RequestError, httpx.RequestError)
    assert issubclass(TimeoutException, httpx.TimeoutException)
    assert issubclass(NetworkError, httpx.NetworkError)


@pytest.mark.asyncio
async def test_request_json_empty_and_no_content():
    """Verify request_json returns {} for 204 or empty/whitespace responses without raising JSONDecodeError."""
    # Async
    mock_httpx_async = AsyncMock(spec=httpx.AsyncClient)
    resp_204 = MagicMock(spec=httpx.Response)
    resp_204.status_code = 204
    resp_204.content = b""
    resp_204.text = ""
    mock_httpx_async.request.return_value = resp_204

    client_async = HTTPClient(client=mock_httpx_async)
    assert await client_async.request_json("PUT", "/endpoint") == {}

    # Sync
    mock_httpx_sync = MagicMock(spec=httpx.Client)
    resp_200_empty = MagicMock(spec=httpx.Response)
    resp_200_empty.status_code = 200
    resp_200_empty.content = b"   "
    resp_200_empty.text = "   "
    mock_httpx_sync.request.return_value = resp_200_empty

    client_sync = SyncHTTPClient(client=mock_httpx_sync)
    assert client_sync.request_json("PUT", "/endpoint") == {}

