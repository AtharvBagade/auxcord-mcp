"""Playback queue inspection and manipulation tools for Auxcord."""

import json
from typing import Any

import httpx

from src.client import get_spotify_client


def _handle_queue_error(exc: Exception) -> str:
    """Format HTTP errors into structured self-healing guidance for LLMs."""
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code == 404:
            return json.dumps(
                {
                    "status": "error",
                    "error_code": "NO_ACTIVE_DEVICE",
                    "message": "No active Spotify device found. Call 'spotify_get_available_devices' to locate an available device and 'spotify_transfer_playback' to activate it.",
                },
                indent=2,
            )
        if status_code == 403:
            return json.dumps(
                {
                    "status": "error",
                    "error_code": "RESTRICTION_VIOLATED",
                    "message": "Queue manipulation requires Spotify Premium or active player permissions.",
                },
                indent=2,
            )
        return json.dumps(
            {
                "status": "error",
                "error_code": f"HTTP_{status_code}",
                "message": f"Spotify API error: {exc.response.text}",
            },
            indent=2,
        )
    return json.dumps(
        {
            "status": "error",
            "error_code": "EXECUTION_ERROR",
            "message": str(exc),
        },
        indent=2,
    )


def _prune_queue_track(item: dict[str, Any] | None) -> dict[str, Any] | None:
    """Prune verbose fields from queue track items."""
    if not item:
        return None
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "artists": [a.get("name") for a in item.get("artists", [])],
        "album": item.get("album", {}).get("name"),
        "duration_ms": item.get("duration_ms"),
        "uri": item.get("uri"),
    }


async def spotify_get_queue() -> str:
    """Fetch the user's current playback queue and currently playing track.

    Returns:
        JSON object containing currently playing track and ordered list of upcoming queue items.
    """
    client = get_spotify_client()
    try:
        raw = await client.get_queue()
        formatted = {
            "currently_playing": _prune_queue_track(raw.get("currently_playing")),
            "queue": [
                _prune_queue_track(item)
                for item in raw.get("queue", [])
                if item is not None
            ],
        }
        return json.dumps(formatted, indent=2)
    except Exception as exc:  # noqa: BLE001
        return _handle_queue_error(exc)


async def spotify_add_to_queue(uri: str, device_id: str | None = None) -> str:
    """Append a track or episode to the user's active Spotify playback queue.

    Args:
        uri: The Spotify URI of the item to add (e.g. "spotify:track:4cOdK2wGLETKBW3PvgPWqT").
        device_id: Optional target Spotify Connect device ID.

    Returns:
        JSON string indicating execution success or error recovery.
    """
    clean_uri = uri.strip()
    if not clean_uri.startswith("spotify:track:") and not clean_uri.startswith("spotify:episode:"):
        # Auto-prefix track ID if only the raw ID was provided
        if ":" not in clean_uri and len(clean_uri) == 22:
            clean_uri = f"spotify:track:{clean_uri}"
        else:
            return json.dumps(
                {
                    "status": "error",
                    "error_code": "INVALID_URI",
                    "message": f"Invalid Spotify URI '{uri}'. Must be in format 'spotify:track:<id>' or 'spotify:episode:<id>'.",
                },
                indent=2,
            )

    client = get_spotify_client()
    try:
        await client.add_to_queue(uri=clean_uri, device_id=device_id)
        return json.dumps(
            {
                "status": "success",
                "message": f"Added '{clean_uri}' to playback queue successfully.",
            },
            indent=2,
        )
    except Exception as exc:  # noqa: BLE001
        return _handle_queue_error(exc)
