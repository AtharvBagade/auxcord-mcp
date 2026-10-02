"""User profile, library, and personalization tools for Spotify MCP Server."""

import json

from src.client import get_spotify_client


async def spotify_get_user_profile() -> str:
    """Fetch current authenticated user's Spotify profile details, country, and subscription status.

    Returns:
        JSON string containing user id, display_name, email, product (Premium/Free), country, followers, and spotify uri.
    """
    client = get_spotify_client()
    profile = await client.get_user_profile()
    return json.dumps(profile, indent=2)


async def spotify_get_top_tracks(
    time_range: str = "medium_term", limit: int = 20, offset: int = 0
) -> str:
    """Fetch user's top listened tracks over short, medium, or long time frames.

    Args:
        time_range: Over what time frame data is calculated ("short_term" ~4wks, "medium_term" ~6mo, "long_term" ~years). Default "medium_term".
        limit: Number of items to return (1-50, default 20).
        offset: Index of first item to return (default 0).

    Returns:
        JSON array of top tracks with track name, artists, album, and URI.
    """
    client = get_spotify_client()
    raw = await client.get_top_tracks(time_range=time_range, limit=limit, offset=offset)

    formatted_tracks = [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "artists": [a.get("name") for a in item.get("artists", [])],
            "album": item.get("album", {}).get("name"),
            "duration_ms": item.get("duration_ms"),
            "uri": item.get("uri"),
        }
        for item in raw.get("items", [])
    ]
    return json.dumps(formatted_tracks, indent=2)


async def spotify_get_top_artists(
    time_range: str = "medium_term", limit: int = 20, offset: int = 0
) -> str:
    """Fetch user's top listened artists over short, medium, or long time frames.

    Args:
        time_range: Time frame ("short_term" ~4wks, "medium_term" ~6mo, "long_term" ~years). Default "medium_term".
        limit: Number of items to return (1-50, default 20).
        offset: Index of first item to return (default 0).

    Returns:
        JSON array of top artists with name and URI.
    """
    client = get_spotify_client()
    raw = await client.get_top_artists(time_range=time_range, limit=limit, offset=offset)

    formatted_artists = [
        {
            "id": item.get("id"),
            "name": item.get("name"),
            "uri": item.get("uri"),
        }
        for item in raw.get("items", [])
    ]
    return json.dumps(formatted_artists, indent=2)


async def spotify_get_recently_played(limit: int = 20) -> str:
    """Fetch user's recently played track history with playback timestamps.

    Args:
        limit: Number of recent items to return (1-50, default 20).

    Returns:
        JSON array of recently played items with played_at timestamp, track details, and context.
    """
    client = get_spotify_client()
    raw = await client.get_recently_played(limit=limit)

    formatted_items = []
    for item in raw.get("items", []):
        track = item.get("track", {})
        formatted_items.append({
            "played_at": item.get("played_at"),
            "track_id": track.get("id"),
            "track_name": track.get("name"),
            "artists": [a.get("name") for a in track.get("artists", [])],
            "album": track.get("album", {}).get("name"),
            "uri": track.get("uri"),
        })

    return json.dumps(formatted_items, indent=2)


async def spotify_get_saved_tracks(limit: int = 20, offset: int = 0) -> str:
    """Fetch tracks saved in user's "Liked Songs" library.

    Args:
        limit: Number of saved tracks to return (1-50, default 20).
        offset: Offset index for pagination (default 0).

    Returns:
        JSON array of saved tracks with added_at timestamp and track metadata.
    """
    client = get_spotify_client()
    raw = await client.get_saved_tracks(limit=limit, offset=offset)

    formatted_items = []
    for item in raw.get("items", []):
        track = item.get("track", {})
        formatted_items.append({
            "added_at": item.get("added_at"),
            "track_id": track.get("id"),
            "track_name": track.get("name"),
            "artists": [a.get("name") for a in track.get("artists", [])],
            "album": track.get("album", {}).get("name"),
            "uri": track.get("uri"),
        })

    return json.dumps(formatted_items, indent=2)
