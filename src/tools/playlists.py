"""Playlist management and custom cover art tools for Spotify MCP Server."""

import base64
import json
import os
from typing import List, Optional
from src.client import get_spotify_client


def normalize_track_uri(track_id_or_uri: str) -> str:
    """Normalize track identifier to a canonical Spotify URI (e.g. spotify:track:xxx)."""
    track_id_or_uri = track_id_or_uri.strip()
    if track_id_or_uri.startswith(("spotify:track:", "spotify:episode:")):
        return track_id_or_uri
    return f"spotify:track:{track_id_or_uri}"


def read_and_validate_jpeg_cover(image_path: str) -> str:
    """Read a local JPEG cover image file, validate file constraints (<= 256 KB), and return base64 string."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Cover image file not found at path: {image_path}")

    if not os.path.isfile(image_path):
        raise ValueError(f"Specified path is not a file: {image_path}")

    file_size = os.path.getsize(image_path)
    max_size_bytes = 256 * 1024  # 256 KB
    if file_size > max_size_bytes:
        raise ValueError(
            f"Cover image file size ({file_size} bytes) exceeds Spotify's maximum limit of 256 KB ({max_size_bytes} bytes)."
        )

    with open(image_path, "rb") as img_file:
        raw_bytes = img_file.read()

    return base64.b64encode(raw_bytes).decode("utf-8")


async def spotify_create_playlist(
    name: str,
    description: str = "",
    public: bool = True,
    collaborative: bool = False,
    user_id: Optional[str] = None,
) -> str:
    """Create a new playlist for the authenticated user.

    Args:
        name: Name of the playlist.
        description: Description of the playlist (default "").
        public: Whether playlist should be public (default True).
        collaborative: Whether playlist should be collaborative (default False).
        user_id: Optional Spotify user ID. If omitted, automatically resolved from current user profile.

    Returns:
        JSON string containing the created playlist's details, ID, URI, and snapshot info.
    """
    client = get_spotify_client()
    raw = await client.create_playlist(
        name=name,
        description=description,
        public=public,
        collaborative=collaborative,
        user_id=user_id,
    )

    formatted = {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "description": raw.get("description"),
        "public": raw.get("public"),
        "collaborative": raw.get("collaborative"),
        "owner": raw.get("owner", {}).get("display_name") or raw.get("owner", {}).get("id"),
        "snapshot_id": raw.get("snapshot_id"),
        "uri": raw.get("uri"),
        "spotify_url": raw.get("external_urls", {}).get("spotify"),
    }
    return json.dumps(formatted, indent=2)


async def spotify_get_user_playlists(limit: int = 20, offset: int = 0) -> str:
    """Fetch playlists owned or followed by the current authenticated user.

    Args:
        limit: Number of playlists to return (1-50, default 20).
        offset: Index of first playlist to return (default 0).

    Returns:
        JSON array of user playlists with metadata, track counts, and URIs.
    """
    client = get_spotify_client()
    raw = await client.get_user_playlists(limit=limit, offset=offset)

    formatted_items = []
    for item in raw.get("items", []):
        images = item.get("images", [])
        image_url = images[0]["url"] if images else None
        formatted_items.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "description": item.get("description"),
            "owner": item.get("owner", {}).get("display_name") or item.get("owner", {}).get("id"),
            "tracks_total": item.get("tracks", {}).get("total", 0),
            "public": item.get("public"),
            "collaborative": item.get("collaborative"),
            "snapshot_id": item.get("snapshot_id"),
            "uri": item.get("uri"),
            "image_url": image_url,
        })

    return json.dumps(formatted_items, indent=2)


async def spotify_get_playlist(playlist_id: str, market: Optional[str] = None) -> str:
    """Fetch complete metadata and first track batch for a specific Spotify playlist.

    Args:
        playlist_id: Spotify playlist ID or URI (e.g. "37i9dQZF1DXcBWIGoYBM5M" or "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M").
        market: Optional ISO 3166-1 alpha-2 country code.

    Returns:
        JSON string containing playlist metadata, follower count, owner details, and track listing.
    """
    clean_id = playlist_id.replace("spotify:playlist:", "").strip()
    client = get_spotify_client()
    raw = await client.get_playlist(clean_id, market=market)

    tracks_data = raw.get("tracks", {})
    formatted_tracks = []
    for item in tracks_data.get("items", []):
        track = item.get("track")
        if track:
            formatted_tracks.append({
                "id": track.get("id"),
                "name": track.get("name"),
                "artists": [a.get("name") for a in track.get("artists", [])],
                "album": track.get("album", {}).get("name"),
                "duration_ms": track.get("duration_ms"),
                "popularity": track.get("popularity"),
                "uri": track.get("uri"),
                "added_at": item.get("added_at"),
            })

    images = raw.get("images", [])
    image_url = images[0]["url"] if images else None

    formatted = {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "description": raw.get("description"),
        "owner": raw.get("owner", {}).get("display_name") or raw.get("owner", {}).get("id"),
        "followers": raw.get("followers", {}).get("total", 0),
        "public": raw.get("public"),
        "collaborative": raw.get("collaborative"),
        "snapshot_id": raw.get("snapshot_id"),
        "total_tracks": tracks_data.get("total", len(formatted_tracks)),
        "uri": raw.get("uri"),
        "spotify_url": raw.get("external_urls", {}).get("spotify"),
        "image_url": image_url,
        "tracks": formatted_tracks,
    }
    return json.dumps(formatted, indent=2)


async def spotify_get_playlist_items(
    playlist_id: str,
    limit: int = 50,
    offset: int = 0,
    market: Optional[str] = None,
) -> str:
    """Fetch paginated tracks/episodes from a playlist.

    Args:
        playlist_id: Spotify playlist ID or URI.
        limit: Number of items to return (1-100, default 50).
        offset: Index of first item to return (default 0).
        market: Optional ISO 3166-1 alpha-2 country code.

    Returns:
        JSON array of tracks inside the playlist with duration, artists, album, and added_at info.
    """
    clean_id = playlist_id.replace("spotify:playlist:", "").strip()
    client = get_spotify_client()
    raw = await client.get_playlist_items(clean_id, limit=limit, offset=offset, market=market)

    formatted_items = []
    for item in raw.get("items", []):
        track = item.get("track")
        if track:
            formatted_items.append({
                "id": track.get("id"),
                "name": track.get("name"),
                "artists": [a.get("name") for a in track.get("artists", [])],
                "album": track.get("album", {}).get("name"),
                "duration_ms": track.get("duration_ms"),
                "popularity": track.get("popularity"),
                "uri": track.get("uri"),
                "added_at": item.get("added_at"),
                "is_local": track.get("is_local", False),
            })

    return json.dumps(formatted_items, indent=2)


async def spotify_add_tracks_to_playlist(
    playlist_id: str,
    uris: List[str],
    position: Optional[int] = None,
) -> str:
    """Add tracks or episodes to a playlist by URI or Spotify track ID.

    Args:
        playlist_id: Spotify playlist ID or URI.
        uris: List of Spotify track URIs (e.g. "spotify:track:xxx") or 22-character track IDs.
        position: Optional zero-based index insertion position.

    Returns:
        JSON string containing mutation status and updated snapshot_id.
    """
    clean_id = playlist_id.replace("spotify:playlist:", "").strip()
    normalized_uris = [normalize_track_uri(u) for u in uris]
    client = get_spotify_client()
    res = await client.add_tracks_to_playlist(clean_id, uris=normalized_uris, position=position)

    return json.dumps(
        {
            "status": "success",
            "playlist_id": clean_id,
            "added_count": len(normalized_uris),
            "snapshot_id": res.get("snapshot_id"),
        },
        indent=2,
    )


async def spotify_remove_tracks_from_playlist(
    playlist_id: str,
    uris: List[str],
    snapshot_id: Optional[str] = None,
) -> str:
    """Remove tracks from a playlist by URI or Spotify track ID.

    Args:
        playlist_id: Spotify playlist ID or URI.
        uris: List of Spotify track URIs (e.g. "spotify:track:xxx") or 22-character track IDs to remove.
        snapshot_id: Optional playlist snapshot ID for optimistic concurrency control.

    Returns:
        JSON string containing mutation status and updated snapshot_id.
    """
    clean_id = playlist_id.replace("spotify:playlist:", "").strip()
    normalized_uris = [normalize_track_uri(u) for u in uris]
    client = get_spotify_client()
    res = await client.remove_tracks_from_playlist(
        clean_id, uris=normalized_uris, snapshot_id=snapshot_id
    )

    return json.dumps(
        {
            "status": "success",
            "playlist_id": clean_id,
            "removed_count": len(normalized_uris),
            "snapshot_id": res.get("snapshot_id"),
        },
        indent=2,
    )


async def spotify_reorder_playlist_tracks(
    playlist_id: str,
    range_start: int,
    insert_before: int,
    range_length: int = 1,
    snapshot_id: Optional[str] = None,
) -> str:
    """Reorder a range of tracks in a playlist to a new position.

    Args:
        playlist_id: Spotify playlist ID or URI.
        range_start: Zero-based position of the first track to be reordered.
        insert_before: Zero-based position where the tracks should be inserted.
        range_length: Number of tracks to reorder (default 1).
        snapshot_id: Optional snapshot ID for concurrency control.

    Returns:
        JSON string containing mutation status and updated snapshot_id.
    """
    clean_id = playlist_id.replace("spotify:playlist:", "").strip()
    client = get_spotify_client()
    res = await client.reorder_playlist_tracks(
        clean_id,
        range_start=range_start,
        insert_before=insert_before,
        range_length=range_length,
        snapshot_id=snapshot_id,
    )

    return json.dumps(
        {
            "status": "success",
            "playlist_id": clean_id,
            "range_start": range_start,
            "insert_before": insert_before,
            "range_length": range_length,
            "snapshot_id": res.get("snapshot_id"),
        },
        indent=2,
    )


async def spotify_replace_playlist_tracks(
    playlist_id: str,
    uris: List[str],
) -> str:
    """Replace all items in a playlist with a new set/sequence of tracks.

    Args:
        playlist_id: Spotify playlist ID or URI.
        uris: Complete list of track URIs or 22-char track IDs to replace existing tracks with.

    Returns:
        JSON string containing mutation status and updated snapshot_id.
    """
    clean_id = playlist_id.replace("spotify:playlist:", "").strip()
    normalized_uris = [normalize_track_uri(u) for u in uris]
    client = get_spotify_client()
    res = await client.replace_playlist_tracks(clean_id, uris=normalized_uris)

    return json.dumps(
        {
            "status": "success",
            "playlist_id": clean_id,
            "total_tracks": len(normalized_uris),
            "snapshot_id": res.get("snapshot_id"),
        },
        indent=2,
    )


async def spotify_update_playlist_details(
    playlist_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    public: Optional[bool] = None,
    collaborative: Optional[bool] = None,
) -> str:
    """Update title, description, or privacy settings of a playlist.

    Args:
        playlist_id: Spotify playlist ID or URI.
        name: New title of the playlist.
        description: New description of the playlist.
        public: Set playlist to public (True) or private (False).
        collaborative: Set playlist to collaborative (True) or non-collaborative (False).

    Returns:
        JSON string containing updated status and modified fields.
    """
    clean_id = playlist_id.replace("spotify:playlist:", "").strip()
    client = get_spotify_client()
    await client.update_playlist_details(
        clean_id,
        name=name,
        description=description,
        public=public,
        collaborative=collaborative,
    )

    updated_fields = {}
    if name is not None:
        updated_fields["name"] = name
    if description is not None:
        updated_fields["description"] = description
    if public is not None:
        updated_fields["public"] = public
    if collaborative is not None:
        updated_fields["collaborative"] = collaborative

    return json.dumps(
        {
            "status": "success",
            "playlist_id": clean_id,
            "updated_fields": updated_fields,
        },
        indent=2,
    )


async def spotify_upload_playlist_cover(
    playlist_id: str,
    image_path: str,
) -> str:
    """Upload a custom JPEG cover image from disk to a Spotify playlist.

    Args:
        playlist_id: Spotify playlist ID or URI.
        image_path: Local file path on disk pointing to a JPEG image file (<= 256 KB).

    Returns:
        JSON string confirming successful cover art upload.
    """
    clean_id = playlist_id.replace("spotify:playlist:", "").strip()
    base64_data = read_and_validate_jpeg_cover(image_path)

    client = get_spotify_client()
    await client.upload_playlist_cover_image(clean_id, base64_image_data=base64_data)

    return json.dumps(
        {
            "status": "success",
            "playlist_id": clean_id,
            "image_path": image_path,
            "message": "Custom playlist cover art uploaded successfully.",
        },
        indent=2,
    )
