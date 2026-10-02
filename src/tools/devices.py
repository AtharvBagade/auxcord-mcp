"""Device discovery and playback transfer tools for Auxcord."""

import json

import httpx

from src.client import get_spotify_client


def _handle_device_error(exc: Exception) -> str:
    """Format HTTP errors into structured self-healing guidance for LLMs."""
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code == 404:
            return json.dumps(
                {
                    "status": "error",
                    "error_code": "DEVICE_NOT_FOUND",
                    "message": "Target Spotify Connect device was not found or is offline.",
                },
                indent=2,
            )
        if status_code == 403:
            return json.dumps(
                {
                    "status": "error",
                    "error_code": "RESTRICTION_VIOLATED",
                    "message": "Target Spotify Connect Device is Restricted",
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


async def spotify_get_available_devices() -> str:
    """Retrieve all available Spotify Connect devices connected to the user's account.

    Returns:
        JSON list of available devices with id, name, type, active status, and volume.
    """
    client = get_spotify_client()
    try:
        raw = await client.get_available_devices()
        devices = [
            {
                "id": d.get("id"),
                "name": d.get("name"),
                "type": d.get("type"),
                "is_active": d.get("is_active", False),
                "is_private_session": d.get("is_private_session", False),
                "is_restricted": d.get("is_restricted", False),
                "volume_percent": d.get("volume_percent"),
            }
            for d in raw.get("devices", [])
        ]
        return json.dumps(devices, indent=2)
    except Exception as exc:  # noqa: BLE001
        return _handle_device_error(exc)


async def spotify_transfer_playback(device_id: str, play: bool = False) -> str:
    """Transfer active playback to a specified Spotify Connect device.

    Args:
        device_id: The target Spotify Connect device ID.
        play: If True, immediately start/resume playback on the target device. If False, keep current play state.

    Returns:
        JSON string indicating execution success or error recovery.
    """
    client = get_spotify_client()
    try:
        await client.transfer_playback(device_id=device_id, play=play)
        return json.dumps(
            {
                "status": "success",
                "message": f"Playback transferred to device '{device_id}' successfully.",
                "play": play,
            },
            indent=2,
        )
    except Exception as exc:  # noqa: BLE001
        return _handle_device_error(exc)
