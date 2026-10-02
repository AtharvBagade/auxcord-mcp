"""Real-time playback control and playback state inspection tools for Spotify MCP Server."""

import json
from typing import Any

import httpx

from src.client import get_spotify_client


def _handle_player_error(exc: Exception) -> str:
    """Format HTTP errors into structured self-healing guidance for LLMs."""
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code == 404:
            return json.dumps(
                {
                    "status": "error",
                    "error_code": "NO_ACTIVE_DEVICE",
                    "message": "No active Spotify device found. Call 'spotify_get_available_devices' to locate an available device and 'spotify_transfer_playback' to activate it, or open Spotify on your device.",
                },
                indent=2,
            )
        if status_code == 403:
            return json.dumps(
                {
                    "status": "error",
                    "error_code": "RESTRICTION_VIOLATED",
                    "message": "Playback control requires Spotify Premium or the active device is currently restricted from this operation.",
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


def _prune_track(item: dict[str, Any] | None) -> dict[str, Any] | None:
    """Prune verbose metadata (available_markets, preview URLs, copyrights) from track objects."""
    if not item:
        return None
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "artists": [a.get("name") for a in item.get("artists", [])],
        "album": item.get("album", {}).get("name"),
        "duration_ms": item.get("duration_ms"),
        "uri": item.get("uri"),
        "is_playable": item.get("is_playable", True),
    }


def _prune_device(device: dict[str, Any] | None) -> dict[str, Any] | None:
    """Prune device object into clean high-signal attributes."""
    if not device:
        return None
    return {
        "id": device.get("id"),
        "name": device.get("name"),
        "type": device.get("type"),
        "is_active": device.get("is_active", False),
        "is_private_session": device.get("is_private_session", False),
        "is_restricted": device.get("is_restricted", False),
        "volume_percent": device.get("volume_percent"),
    }


async def spotify_play(
    device_id: str | None = None,
    context_uri: str | None = None,
    uris: list[str] | None = None,
    offset_position: int | None = None,
    offset_uri: str | None = None,
    position_ms: int | None = None,
) -> str:
    """Start a new context/tracklist or resume current playback.

    Args:
        device_id: Optional target Spotify Connect device ID.
        context_uri: Optional Spotify URI of playlist, album, or artist to play.
        uris: Optional list of Spotify track/episode URIs to play (mutually exclusive with context_uri).
        offset_position: Optional 0-indexed track position to start from within context_uri.
        offset_uri: Optional track URI to start from within context_uri or uris.
        position_ms: Optional timestamp in milliseconds to start playback from.

    Returns:
        JSON string indicating execution success or structured error recovery.
    """
    client = get_spotify_client()
    offset: dict[str, Any] | None = None
    if offset_position is not None:
        offset = {"position": offset_position}
    elif offset_uri is not None:
        offset = {"uri": offset_uri}

    try:
        await client.play(
            device_id=device_id,
            context_uri=context_uri,
            uris=uris,
            offset=offset,
            position_ms=position_ms,
        )
        return json.dumps(
            {"status": "success", "message": "Playback started or resumed successfully."},
            indent=2,
        )
    except Exception as exc:  # noqa: BLE001
        return _handle_player_error(exc)


async def spotify_pause(device_id: str | None = None) -> str:
    """Pause playback on the active Spotify device.

    Args:
        device_id: Optional target Spotify Connect device ID.

    Returns:
        JSON string indicating execution success or structured error recovery.
    """
    client = get_spotify_client()
    try:
        await client.pause(device_id=device_id)
        return json.dumps(
            {"status": "success", "message": "Playback paused successfully."},
            indent=2,
        )
    except Exception as exc:  # noqa: BLE001
        return _handle_player_error(exc)


async def spotify_skip_to_next(device_id: str | None = None) -> str:
    """Skip to the next track in the user's queue or active context.

    Args:
        device_id: Optional target Spotify Connect device ID.

    Returns:
        JSON string indicating execution success or structured error recovery.
    """
    client = get_spotify_client()
    try:
        await client.skip_to_next(device_id=device_id)
        return json.dumps(
            {"status": "success", "message": "Skipped to next track."},
            indent=2,
        )
    except Exception as exc:  # noqa: BLE001
        return _handle_player_error(exc)


async def spotify_skip_to_previous(device_id: str | None = None) -> str:
    """Skip to the previous track in the user's active context.

    Args:
        device_id: Optional target Spotify Connect device ID.

    Returns:
        JSON string indicating execution success or structured error recovery.
    """
    client = get_spotify_client()
    try:
        await client.skip_to_previous(device_id=device_id)
        return json.dumps(
            {"status": "success", "message": "Skipped to previous track."},
            indent=2,
        )
    except Exception as exc:  # noqa: BLE001
        return _handle_player_error(exc)


async def spotify_seek_to_position(position_ms: int, device_id: str | None = None) -> str:
    """Seek to a specific timestamp in the currently playing track.

    Args:
        position_ms: Position in milliseconds to seek to (e.g. 30000 for 30 seconds).
        device_id: Optional target Spotify Connect device ID.

    Returns:
        JSON string indicating execution success or structured error recovery.
    """
    client = get_spotify_client()
    try:
        await client.seek_to_position(position_ms=position_ms, device_id=device_id)
        return json.dumps(
            {
                "status": "success",
                "message": f"Seeked to position {position_ms} ms successfully.",
            },
            indent=2,
        )
    except Exception as exc:  # noqa: BLE001
        return _handle_player_error(exc)


async def spotify_set_volume(volume_percent: int, device_id: str | None = None) -> str:
    """Set the playback volume percentage on the active device.

    Args:
        volume_percent: Volume level percentage from 0 to 100.
        device_id: Optional target Spotify Connect device ID.

    Returns:
        JSON string indicating execution success or structured error recovery.
    """
    if volume_percent < 0 or volume_percent > 100:
        return json.dumps(
            {
                "status": "error",
                "error_code": "INVALID_ARGUMENT",
                "message": "volume_percent must be an integer between 0 and 100.",
            },
            indent=2,
        )
    client = get_spotify_client()
    try:
        await client.set_volume(volume_percent=volume_percent, device_id=device_id)
        return json.dumps(
            {
                "status": "success",
                "message": f"Volume set to {volume_percent}% successfully.",
            },
            indent=2,
        )
    except Exception as exc:  # noqa: BLE001
        return _handle_player_error(exc)


async def spotify_toggle_shuffle(state: bool, device_id: str | None = None) -> str:
    """Toggle shuffle mode on or off.

    Args:
        state: True to turn shuffle on, False to turn shuffle off.
        device_id: Optional target Spotify Connect device ID.

    Returns:
        JSON string indicating execution success or structured error recovery.
    """
    client = get_spotify_client()
    try:
        await client.toggle_shuffle(state=state, device_id=device_id)
        mode = "on" if state else "off"
        return json.dumps(
            {"status": "success", "message": f"Shuffle mode turned {mode}."},
            indent=2,
        )
    except Exception as exc:  # noqa: BLE001
        return _handle_player_error(exc)


async def spotify_set_repeat_mode(state: str, device_id: str | None = None) -> str:
    """Set the playback repeat mode ('off', 'track', 'context').

    Args:
        state: Repeat mode option ('off', 'track', 'context').
        device_id: Optional target Spotify Connect device ID.

    Returns:
        JSON string indicating execution success or structured error recovery.
    """
    valid_modes = {"off", "track", "context"}
    clean_state = state.strip().lower()
    if clean_state not in valid_modes:
        return json.dumps(
            {
                "status": "error",
                "error_code": "INVALID_ARGUMENT",
                "message": f"Invalid repeat mode '{state}'. Must be one of: {sorted(valid_modes)}.",
            },
            indent=2,
        )
    client = get_spotify_client()
    try:
        await client.set_repeat_mode(state=clean_state, device_id=device_id)
        return json.dumps(
            {
                "status": "success",
                "message": f"Repeat mode set to '{clean_state}' successfully.",
            },
            indent=2,
        )
    except Exception as exc:  # noqa: BLE001
        return _handle_player_error(exc)


async def spotify_get_playback_state(market: str | None = None) -> str:
    """Retrieve the current playback state including active device, track info, progress, and modes.

    Args:
        market: Optional ISO 3166-1 alpha-2 country code.

    Returns:
        JSON string with pruned, high-signal player state metadata.
    """
    client = get_spotify_client()
    try:
        raw = await client.get_playback_state(market=market)
        if not raw:
            return json.dumps(
                {
                    "is_playing": False,
                    "device": None,
                    "item": None,
                    "message": "No active playback session found.",
                },
                indent=2,
            )

        formatted = {
            "is_playing": raw.get("is_playing", False),
            "progress_ms": raw.get("progress_ms"),
            "shuffle_state": raw.get("shuffle_state", False),
            "repeat_state": raw.get("repeat_state", "off"),
            "currently_playing_type": raw.get("currently_playing_type"),
            "device": _prune_device(raw.get("device")),
            "item": _prune_track(raw.get("item")),
            "context": {
                "type": raw.get("context", {}).get("type") if raw.get("context") else None,
                "uri": raw.get("context", {}).get("uri") if raw.get("context") else None,
            }
            if raw.get("context")
            else None,
        }
        return json.dumps(formatted, indent=2)
    except Exception as exc:  # noqa: BLE001
        return _handle_player_error(exc)


async def spotify_get_currently_playing(market: str | None = None) -> str:
    """Retrieve the currently playing track or episode with playback progress.

    Args:
        market: Optional ISO 3166-1 alpha-2 country code.

    Returns:
        JSON string with lightweight track metadata and progress.
    """
    client = get_spotify_client()
    try:
        raw = await client.get_currently_playing(market=market)
        if not raw or not raw.get("item"):
            return json.dumps(
                {
                    "is_playing": False,
                    "item": None,
                    "message": "Nothing is currently playing.",
                },
                indent=2,
            )

        formatted = {
            "is_playing": raw.get("is_playing", False),
            "progress_ms": raw.get("progress_ms"),
            "currently_playing_type": raw.get("currently_playing_type"),
            "item": _prune_track(raw.get("item")),
        }
        return json.dumps(formatted, indent=2)
    except Exception as exc:  # noqa: BLE001
        return _handle_player_error(exc)
