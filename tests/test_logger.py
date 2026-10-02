"""Unit tests for src.lib.logger (hook A helpers, hook B tool-call wrapper, transport mode)."""

import logging
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.lib.logger import get_transport_mode, log_tool_calls, logger, set_transport_mode


@pytest.fixture(autouse=True)
def _reset_transport_mode():
    """Module-level transport mode is global state -- save/restore across tests."""
    original = get_transport_mode()
    yield
    set_transport_mode(original)


@pytest.mark.asyncio
async def test_log_tool_calls_logs_info_on_success(caplog):
    """Hook B logs a terse INFO line on a successful tool call."""

    async def dummy_tool(x: int) -> int:
        return x * 2

    wrapped = log_tool_calls(dummy_tool)

    with caplog.at_level(logging.INFO, logger="spotify_mcp"):
        result = await wrapped(21)

    assert result == 42
    ok_records = [r for r in caplog.records if "TOOL_CALL_OK" in r.message]
    assert len(ok_records) == 1
    assert "tool=dummy_tool" in ok_records[0].message
    assert "duration_ms=" in ok_records[0].message
    assert not any("TOOL_CALL_FAILED" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_log_tool_calls_logs_error_and_reraises(caplog):
    """Hook B logs an ERROR block on an uncaught exception and re-raises it unchanged.

    At INFO (the default level), the full stack trace is suppressed to keep
    stderr quiet -- only the terse exception type/message is logged.
    """

    async def failing_tool(name: str = "x") -> str:
        raise ValueError("boom")

    wrapped = log_tool_calls(failing_tool)

    with caplog.at_level(logging.INFO, logger="spotify_mcp"):
        with pytest.raises(ValueError, match="boom"):
            await wrapped(name="y")

    failed_records = [r for r in caplog.records if "TOOL_CALL_FAILED" in r.message]
    assert len(failed_records) == 1
    message = failed_records[0].message
    assert "tool=failing_tool" in message
    assert "ValueError: boom" in message
    assert "Traceback" not in message


@pytest.mark.asyncio
async def test_log_tool_calls_includes_traceback_at_debug_level(caplog):
    """At DEBUG level, hook B includes the full stack trace for an uncaught exception."""

    async def failing_tool(name: str = "x") -> str:
        raise ValueError("boom")

    wrapped = log_tool_calls(failing_tool)

    with caplog.at_level(logging.DEBUG, logger="spotify_mcp"), pytest.raises(ValueError, match="boom"):
        await wrapped(name="y")

    failed_records = [r for r in caplog.records if "TOOL_CALL_FAILED" in r.message]
    assert len(failed_records) == 1
    assert "Traceback" in failed_records[0].message


def test_logger_handlers_target_stderr_not_stdout():
    """Every handler on the spotify_mcp logger writes to fd 2 (stderr), never fd 1 (stdout).

    stdio transport uses stdout for JSON-RPC protocol frames, so this is a
    hard architectural invariant. Checked via OS file descriptor number
    rather than Python object identity against sys.stderr: pytest's own
    capture machinery (and, since our logger has propagate=False, pytest's
    caplog fixture attaches its own handlers directly onto this named
    logger to still intercept records) can swap in new stream wrapper
    objects per test, so identity checks against sys.stderr are unreliable
    here -- but the underlying OS descriptor number is not.
    """
    stream_handlers = [
        h
        for h in logger.handlers
        if isinstance(h, logging.StreamHandler) and hasattr(h.stream, "fileno")
    ]
    assert len(stream_handlers) >= 1
    for handler in stream_handlers:
        try:
            fd = handler.stream.fileno()
        except (OSError, ValueError):
            continue  # not a real OS stream (e.g. an in-memory capture buffer) -- skip
        assert fd != 1, "a spotify_mcp log handler is writing to stdout (fd 1)"


def test_set_and_get_transport_mode():
    """set_transport_mode / get_transport_mode round-trip correctly."""
    set_transport_mode("http")
    assert get_transport_mode() == "http"
    set_transport_mode("stdio")
    assert get_transport_mode() == "stdio"


@pytest.mark.asyncio
async def test_log_tool_calls_includes_transport_mode(caplog):
    """Log lines include the currently configured transport mode."""
    set_transport_mode("http")

    async def dummy_tool() -> str:
        return "ok"

    wrapped = log_tool_calls(dummy_tool)

    with caplog.at_level(logging.INFO, logger="spotify_mcp"):
        await wrapped()

    assert any("mode=http" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_self_healing_tool_logs_api_failure_but_ok_at_tool_level(caplog):
    """Integration: a player tool that self-heals a 404 still logs the raw API
    failure at hook A (SpotifyClient.request), while hook B logs the wrapped
    tool call itself as OK, since no exception escapes the tool."""
    from src.client import SpotifyClient
    from src.tools.playback import spotify_play

    resp = MagicMock()
    resp.status_code = 404
    resp.text = '{"error": {"status": 404, "message": "Device not found"}}'
    resp.content = resp.text.encode()

    http_request = httpx.Request("PUT", "https://api.spotify.com/v1/me/player/play")
    real_response = httpx.Response(404, request=http_request, text=resp.text)
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404 error", request=http_request, response=real_response
    )

    mock_auth_manager = MagicMock()
    mock_auth_manager.get_valid_access_token.return_value = "mock_token"
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=resp)
    real_client = SpotifyClient(auth_manager=mock_auth_manager, http_client=mock_http)

    with patch("src.tools.playback.get_spotify_client", return_value=real_client):
        wrapped = log_tool_calls(spotify_play)

        with caplog.at_level(logging.INFO, logger="spotify_mcp"):
            result = await wrapped(context_uri="spotify:album:abc123")

    # (a) the wrapped tool call returns normally -- the self-healed JSON string,
    # no exception propagates out of the tool.
    assert "NO_ACTIVE_DEVICE" in result

    # (b) hook A still logged the raw API failure at its source.
    api_failure_records = [r for r in caplog.records if "SPOTIFY_API_FAILURE" in r.message]
    assert len(api_failure_records) == 1
    assert "404" in api_failure_records[0].message

    # (c) hook B sees a normal return value -- logs OK, not FAILED.
    ok_records = [r for r in caplog.records if "TOOL_CALL_OK" in r.message]
    failed_records = [r for r in caplog.records if "TOOL_CALL_FAILED" in r.message]
    assert len(ok_records) == 1
    assert len(failed_records) == 0
