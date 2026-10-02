"""Client-side argument validation and structured errors for Spotify 400 responses.

Limits mirror what the live Web API enforces (verified 2026-10); Spotify answers anything
outside them with a 400. Checking first gives agents an actionable message without a round trip.
"""

import functools
import json
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

SEARCH_MAX_LIMIT = 10
SEARCH_MAX_WINDOW = 1000  # limit + offset
PAGED_MAX_LIMIT = 50  # top items, recently played, saved tracks, user playlists
PLAYLIST_ITEMS_MAX_LIMIT = 100
TIME_RANGES = ("short_term", "medium_term", "long_term")
SEARCH_TYPES = ("album", "artist", "playlist", "track", "show", "episode", "audiobook")


def invalid_argument(message: str) -> str:
    """Structured error for arguments Spotify would reject."""
    return json.dumps({"status": "error", "error_code": "INVALID_ARGUMENT", "message": message}, indent=2)


def check_paging(limit: int, offset: int = 0, max_limit: int = PAGED_MAX_LIMIT) -> str | None:
    """Return a structured error if limit/offset are out of range, else None."""
    if not 1 <= limit <= max_limit:
        return invalid_argument(f"limit must be between 1 and {max_limit} (got {limit}).")
    if offset < 0:
        return invalid_argument(f"offset must be 0 or greater (got {offset}).")
    return None


def check_time_range(time_range: str) -> str | None:
    if time_range not in TIME_RANGES:
        return invalid_argument(f"Invalid time_range '{time_range}'. Must be one of: {list(TIME_RANGES)}.")
    return None


def structured_bad_request(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
    """Turn a Spotify 400 that escaped validation into a structured error carrying Spotify's message."""

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return await fn(*args, **kwargs)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 400:
                raise
            try:
                detail = exc.response.json()["error"]["message"]
            except (ValueError, KeyError, TypeError):
                detail = exc.response.text
            return json.dumps(
                {
                    "status": "error",
                    "error_code": "SPOTIFY_BAD_REQUEST",
                    "message": f"Spotify rejected the request: {detail}",
                },
                indent=2,
            )

    return wrapper
