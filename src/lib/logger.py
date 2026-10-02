"""Plain-text stderr logging utility for Spotify MCP Server.

Two hook points write through this module:
  A. src/client.py SpotifyClient.request() -- logs raw Spotify API failures
     at the source, before any caller has a chance to self-heal them.
  B. src/mcp_server.py tool registration wrapper -- logs one line per
     successful tool call, and a verbose block for any exception that
     propagates out of a tool uncaught.

See docs/adr/0004-two-hook-point-request-logging.md for rationale.

Logs are always written to stderr, never stdout: stdio transport uses
stdout for JSON-RPC protocol frames, so anything else written there would
corrupt the protocol stream.
"""

import functools
import logging
import sys
import time
import traceback
from typing import Any, Awaitable, Callable, TypeVar

from src.config import load_settings

_LOGGER_NAME = "spotify_mcp"

# Module-level transport mode, set once by main.py / mcp_server.py before
# mcp.run(). A plain global rather than a contextvar: this process runs
# exactly one transport mode for its whole lifetime, set once at startup.
_transport_mode: str = "unknown"


def set_transport_mode(mode: str) -> None:
    """Set the current transport mode ('stdio' or 'http'). Call once at startup."""
    global _transport_mode
    _transport_mode = mode


def get_transport_mode() -> str:
    """Return the currently configured transport mode."""
    return _transport_mode


def _build_logger() -> logging.Logger:
    level_name = load_settings().log_level.upper()
    level = getattr(logging, level_name, logging.INFO)

    log = logging.getLogger(_LOGGER_NAME)
    log.setLevel(level)
    if not log.handlers:  # idempotent -- safe if this module is imported multiple times
        handler = logging.StreamHandler(stream=sys.stderr)
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        log.addHandler(handler)
        log.propagate = False  # never let it bubble to root -> stdout risk
    return log


logger = _build_logger()


# --- Hook A: source-level Spotify API error logging ------------------------

def log_api_error(
    *,
    method: str,
    endpoint: str,
    status_code: int | None,
    error_message: str,
    params: dict[str, Any] | None,
    payload: Any | None,
) -> None:
    """Log a verbose ERROR block for a raw Spotify Web API failure (hook A)."""
    logger.error(
        "SPOTIFY_API_FAILURE mode=%s method=%s endpoint=%s status=%s\n"
        "    error: %s\n"
        "    params: %s\n"
        "    payload: %s",
        _transport_mode,
        method.upper(),
        endpoint,
        status_code if status_code is not None else "N/A",
        error_message,
        params,
        payload,
    )


# --- Hook B: tool registration wrapper --------------------------------------

F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def log_tool_calls(fn: F) -> F:
    """Wrap an MCP tool coroutine function with call logging (hook B).

    Success -> terse INFO one-liner.
    Uncaught exception -> verbose ERROR block, then re-raised unchanged.
    """
    tool_name = fn.__name__

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.monotonic()
        try:
            result = await fn(*args, **kwargs)
            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "TOOL_CALL_OK mode=%s tool=%s duration_ms=%.1f",
                _transport_mode,
                tool_name,
                duration_ms,
            )
            return result
        except Exception as exc:  # noqa: BLE001 -- must log any propagating exception
            duration_ms = (time.monotonic() - start) * 1000
            # Full stack trace only at DEBUG -- at INFO+ this would spam stderr
            # with noise for errors tools already handle/report structurally.
            trace = traceback.format_exc() if logger.isEnabledFor(logging.DEBUG) else "(set LOG_LEVEL=DEBUG for traceback)"
            logger.error(
                "TOOL_CALL_FAILED mode=%s tool=%s duration_ms=%.1f\n"
                "    args: %s\n"
                "    kwargs: %s\n"
                "    exception: %s: %s\n"
                "%s",
                _transport_mode,
                tool_name,
                duration_ms,
                args,
                kwargs,
                type(exc).__name__,
                exc,
                trace,
            )
            raise

    return wrapper  # type: ignore[return-value]
