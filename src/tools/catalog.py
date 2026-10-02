"""Catalog search and metadata retrieval tools for Auxcord."""

import json
from typing import Any

from src.client import get_spotify_client
from src.tools.validation import (
    SEARCH_MAX_LIMIT,
    SEARCH_MAX_WINDOW,
    SEARCH_TYPES,
    check_paging,
    invalid_argument,
)


async def spotify_search_catalog(
    query: str,
    search_types: list[str] | None = None,
    limit: int = 5,
    offset: int = 0,
    market: str | None = None,
) -> str:
    """Search the Spotify catalog across tracks, artists, albums, playlists, etc.

    Args:
        query: Search query string (e.g. "Daft Punk", "Bohemian Rhapsody").
        search_types: Optional list of item types to search ("track", "artist", "album", "playlist", "show", "episode", "audiobook"). Defaults to ["track", "artist", "album"].
        limit: Number of items per type to return (1-10, default 5).
        offset: Result offset index (default 0); limit + offset must not exceed 1000.
        market: Optional ISO 3166-1 alpha-2 country code (e.g. "US").

    Returns:
        JSON string of matching search items grouped by category.
    """
    if not query.strip():
        return invalid_argument("query must not be empty.")
    if search_types:
        unknown = [t for t in search_types if t not in SEARCH_TYPES]
        if unknown:
            return invalid_argument(f"Invalid search_types {unknown}. Must be any of: {list(SEARCH_TYPES)}.")
    if error := check_paging(limit, offset, max_limit=SEARCH_MAX_LIMIT):
        return error
    if limit + offset > SEARCH_MAX_WINDOW:
        return invalid_argument(f"limit + offset must not exceed {SEARCH_MAX_WINDOW} (got {limit + offset}).")
    client = get_spotify_client()
    raw_results = await client.search_catalog(
        query=query,
        search_types=search_types,
        limit=limit,
        offset=offset,
        market=market,
    )

    formatted_results: dict[str, Any] = {}

    if "tracks" in raw_results:
        formatted_results["tracks"] = [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "artists": [a.get("name") for a in item.get("artists", [])],
                "album": item.get("album", {}).get("name"),
                "duration_ms": item.get("duration_ms"),
                "uri": item.get("uri"),
            }
            for item in raw_results["tracks"].get("items", [])
            if item
        ]

    if "artists" in raw_results:
        formatted_results["artists"] = [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "uri": item.get("uri"),
            }
            for item in raw_results["artists"].get("items", [])
            if item
        ]

    if "albums" in raw_results:
        formatted_results["albums"] = [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "artists": [a.get("name") for a in item.get("artists", [])],
                "release_date": item.get("release_date"),
                "total_tracks": item.get("total_tracks"),
                "uri": item.get("uri"),
            }
            for item in raw_results["albums"].get("items", [])
            if item
        ]

    if "playlists" in raw_results:
        playlist_items = raw_results["playlists"].get("items", [])
        formatted_results["playlists"] = [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "owner": item.get("owner", {}).get("display_name"),
                "tracks_total": (item.get("items") or {}).get("total", 0),
                "uri": item.get("uri"),
            }
            for item in playlist_items
            if item
        ]
        # Spotify returns null entries for playlists it won't show this app. Report the count so a
        # mostly-hidden page isn't mistaken for "no matches" -- the next offset may still have results.
        hidden = len(playlist_items) - len(formatted_results["playlists"])
        if hidden:
            formatted_results["playlists_hidden_by_spotify"] = hidden

    return json.dumps(formatted_results, indent=2)


async def spotify_get_artist(artist_id: str) -> str:
    """Fetch metadata for a specific Spotify artist.

    Args:
        artist_id: The Spotify ID or URI for the artist.

    Returns:
        JSON string containing artist name, URI, Spotify URL, and image.
    """
    clean_id = artist_id.replace("spotify:artist:", "")
    client = get_spotify_client()
    raw = await client.get_artist(clean_id)

    images = raw.get("images", [])
    image_url = images[0]["url"] if images else None

    formatted = {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "uri": raw.get("uri"),
        "spotify_url": raw.get("external_urls", {}).get("spotify"),
        "image_url": image_url,
    }
    return json.dumps(formatted, indent=2)


async def spotify_get_album(album_id: str) -> str:
    """Fetch metadata and complete tracklist for a Spotify album.

    Args:
        album_id: The Spotify ID or URI for the album.

    Returns:
        JSON string containing album name, artists, release date, and tracks list.
    """
    clean_id = album_id.replace("spotify:album:", "")
    client = get_spotify_client()
    raw = await client.get_album(clean_id)

    tracks = [
        {
            "id": t.get("id"),
            "track_number": t.get("track_number"),
            "name": t.get("name"),
            "duration_ms": t.get("duration_ms"),
            "artists": [a.get("name") for a in t.get("artists", [])],
            "uri": t.get("uri"),
        }
        for t in raw.get("tracks", {}).get("items", [])
    ]

    formatted = {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "album_type": raw.get("album_type"),
        "artists": [a.get("name") for a in raw.get("artists", [])],
        "release_date": raw.get("release_date"),
        "total_tracks": raw.get("total_tracks"),
        "uri": raw.get("uri"),
        "tracks": tracks,
    }
    return json.dumps(formatted, indent=2)
