"""Unit tests for playlist management tools, cover art upload, client methods, and MCP resources."""

import base64
import json
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.client import SpotifyClient
from src.mcp_server import get_playlist_resource
from src.tools.playlists import (
    normalize_track_uri,
    read_and_validate_jpeg_cover,
    spotify_add_tracks_to_playlist,
    spotify_create_playlist,
    spotify_get_playlist,
    spotify_get_playlist_items,
    spotify_get_user_playlists,
    spotify_remove_tracks_from_playlist,
    spotify_reorder_playlist_tracks,
    spotify_replace_playlist_tracks,
    spotify_update_playlist_details,
    spotify_upload_playlist_cover,
)


# --- Helper Function Tests ---

def test_normalize_track_uri():
    """Test URI normalization for track IDs, URIs, and episodes."""
    assert normalize_track_uri("spotify:track:4iV5W9uYEdYUVa79Axb7Rh") == "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"
    assert normalize_track_uri("spotify:episode:512PQ0FwOPu40T431VVGz8") == "spotify:episode:512PQ0FwOPu40T431VVGz8"
    assert normalize_track_uri("4iV5W9uYEdYUVa79Axb7Rh") == "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"
    assert normalize_track_uri("  4iV5W9uYEdYUVa79Axb7Rh  ") == "spotify:track:4iV5W9uYEdYUVa79Axb7Rh"


def test_read_and_validate_jpeg_cover_valid():
    """Test reading valid JPEG cover file within 256KB."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        sample_bytes = b"fake_jpeg_image_data_bytes"
        tmp.write(sample_bytes)
        tmp_path = tmp.name

    try:
        b64 = read_and_validate_jpeg_cover(tmp_path)
        assert b64 == base64.b64encode(sample_bytes).decode("utf-8")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_read_and_validate_jpeg_cover_not_found():
    """Test error on missing cover image file."""
    with pytest.raises(FileNotFoundError):
        read_and_validate_jpeg_cover("/non/existent/path/cover.jpg")


def test_read_and_validate_jpeg_cover_size_exceeded():
    """Test error when cover image file exceeds 256KB limit."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        large_bytes = b"a" * (256 * 1024 + 10)  # > 256KB
        tmp.write(large_bytes)
        tmp_path = tmp.name

    try:
        with pytest.raises(ValueError, match="exceeds Spotify's maximum limit"):
            read_and_validate_jpeg_cover(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# --- SpotifyClient Playlist Methods Tests ---

@pytest.mark.asyncio
async def test_client_create_playlist_explicit_user():
    """Test SpotifyClient.create_playlist with explicit user_id."""
    client = SpotifyClient(auth_manager=MagicMock())
    with patch.object(client, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"id": "pl1", "name": "Vibe Mix"}
        res = await client.create_playlist(name="Vibe Mix", description="Chill vibes", public=True, collaborative=False, user_id="user123")

        mock_req.assert_awaited_once_with(
            "POST",
            "/users/user123/playlists",
            json_data={"name": "Vibe Mix", "description": "Chill vibes", "public": True, "collaborative": False},
        )
        assert res["id"] == "pl1"


@pytest.mark.asyncio
async def test_client_create_playlist_auto_resolve_user():
    """Test SpotifyClient.create_playlist auto-resolving user ID from profile."""
    client = SpotifyClient(auth_manager=MagicMock())
    with patch.object(client, "get_user_profile", new_callable=AsyncMock) as mock_prof, \
         patch.object(client, "request", new_callable=AsyncMock) as mock_req:
        mock_prof.return_value = {"id": "auto_user_456"}
        mock_req.return_value = {"id": "pl2", "name": "Auto Playlist"}

        res = await client.create_playlist(name="Auto Playlist")

        mock_prof.assert_awaited_once()
        mock_req.assert_awaited_once_with(
            "POST",
            "/users/auto_user_456/playlists",
            json_data={"name": "Auto Playlist", "description": "", "public": True, "collaborative": False},
        )
        assert res["id"] == "pl2"


@pytest.mark.asyncio
async def test_client_playlist_mutation_methods():
    """Test SpotifyClient playlist query and mutation methods."""
    client = SpotifyClient(auth_manager=MagicMock())
    with patch.object(client, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {"snapshot_id": "snap123"}

        # get_user_playlists
        await client.get_user_playlists(limit=10, offset=5)
        mock_req.assert_awaited_with("GET", "/me/playlists", params={"limit": 10, "offset": 5})

        # get_playlist
        await client.get_playlist(playlist_id="pl123", market="US")
        mock_req.assert_awaited_with("GET", "/playlists/pl123", params={"market": "US"})

        # get_playlist_items
        await client.get_playlist_items(playlist_id="pl123", limit=25, offset=10)
        mock_req.assert_awaited_with("GET", "/playlists/pl123/tracks", params={"limit": 25, "offset": 10})

        # add_tracks_to_playlist
        await client.add_tracks_to_playlist(playlist_id="pl123", uris=["spotify:track:t1"], position=0)
        mock_req.assert_awaited_with("POST", "/playlists/pl123/tracks", json_data={"uris": ["spotify:track:t1"], "position": 0})

        # remove_tracks_from_playlist
        await client.remove_tracks_from_playlist(playlist_id="pl123", uris=["spotify:track:t1"], snapshot_id="snap123")
        mock_req.assert_awaited_with(
            "DELETE",
            "/playlists/pl123/tracks",
            json_data={"tracks": [{"uri": "spotify:track:t1"}], "snapshot_id": "snap123"},
        )

        # reorder_playlist_tracks
        await client.reorder_playlist_tracks(playlist_id="pl123", range_start=2, insert_before=0, range_length=1, snapshot_id="snap123")
        mock_req.assert_awaited_with(
            "PUT",
            "/playlists/pl123/tracks",
            json_data={"range_start": 2, "insert_before": 0, "range_length": 1, "snapshot_id": "snap123"},
        )

        # replace_playlist_tracks
        await client.replace_playlist_tracks(playlist_id="pl123", uris=["spotify:track:t1", "spotify:track:t2"])
        mock_req.assert_awaited_with("PUT", "/playlists/pl123/tracks", json_data={"uris": ["spotify:track:t1", "spotify:track:t2"]})

        # update_playlist_details
        await client.update_playlist_details(playlist_id="pl123", name="New Name", description="New Desc", public=False)
        mock_req.assert_awaited_with(
            "PUT",
            "/playlists/pl123",
            json_data={"name": "New Name", "description": "New Desc", "public": False},
        )

        # upload_playlist_cover_image
        await client.upload_playlist_cover_image(playlist_id="pl123", base64_image_data="base64str")
        mock_req.assert_awaited_with(
            "PUT",
            "/playlists/pl123/images",
            headers={"Content-Type": "image/jpeg"},
            data="base64str",
        )


# --- MCP Playlist Tool Function Tests ---

@pytest.mark.asyncio
async def test_spotify_create_playlist_tool():
    """Test spotify_create_playlist tool output formatting."""
    mock_res = {
        "id": "pl_abc",
        "name": "Synthwave Night",
        "description": "Retro electro sounds",
        "public": True,
        "collaborative": False,
        "owner": {"display_name": "RetroMaster"},
        "snapshot_id": "snap_1",
        "uri": "spotify:playlist:pl_abc",
        "external_urls": {"spotify": "https://open.spotify.com/playlist/pl_abc"},
    }

    with patch("src.tools.playlists.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.create_playlist = AsyncMock(return_value=mock_res)
        mock_get_client.return_value = mock_client

        output = await spotify_create_playlist(name="Synthwave Night", description="Retro electro sounds")
        data = json.loads(output)

        assert data["id"] == "pl_abc"
        assert data["name"] == "Synthwave Night"
        assert data["owner"] == "RetroMaster"
        assert data["snapshot_id"] == "snap_1"


@pytest.mark.asyncio
async def test_spotify_get_user_playlists_tool():
    """Test spotify_get_user_playlists tool output formatting."""
    mock_res = {
        "items": [
            {
                "id": "pl1",
                "name": "Chill House",
                "description": "Deep vibes",
                "owner": {"display_name": "DJ"},
                "tracks": {"total": 45},
                "public": True,
                "collaborative": False,
                "snapshot_id": "snap_ch",
                "uri": "spotify:playlist:pl1",
                "images": [{"url": "https://img.com/cover.jpg"}],
            }
        ]
    }

    with patch("src.tools.playlists.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_user_playlists = AsyncMock(return_value=mock_res)
        mock_get_client.return_value = mock_client

        output = await spotify_get_user_playlists(limit=10)
        data = json.loads(output)

        assert len(data) == 1
        assert data[0]["name"] == "Chill House"
        assert data[0]["tracks_total"] == 45
        assert data[0]["image_url"] == "https://img.com/cover.jpg"


@pytest.mark.asyncio
async def test_spotify_get_playlist_tool():
    """Test spotify_get_playlist tool output formatting."""
    mock_res = {
        "id": "pl_full",
        "name": "Full Mix",
        "description": "Great hits",
        "owner": {"display_name": "Curator"},
        "followers": {"total": 1200},
        "public": True,
        "collaborative": False,
        "snapshot_id": "snap_full",
        "uri": "spotify:playlist:pl_full",
        "external_urls": {"spotify": "https://open.spotify.com/playlist/pl_full"},
        "images": [{"url": "https://img.com/full.jpg"}],
        "tracks": {
            "total": 1,
            "items": [
                {
                    "added_at": "2026-08-01T00:00:00Z",
                    "track": {
                        "id": "t10",
                        "name": "Track Ten",
                        "artists": [{"name": "Artist Ten"}],
                        "album": {"name": "Album Ten"},
                        "duration_ms": 180000,
                        "popularity": 80,
                        "uri": "spotify:track:t10",
                    },
                }
            ],
        },
    }

    with patch("src.tools.playlists.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_playlist = AsyncMock(return_value=mock_res)
        mock_get_client.return_value = mock_client

        output = await spotify_get_playlist("spotify:playlist:pl_full")
        data = json.loads(output)

        assert data["id"] == "pl_full"
        assert data["followers"] == 1200
        assert len(data["tracks"]) == 1
        assert data["tracks"][0]["name"] == "Track Ten"
        mock_client.get_playlist.assert_awaited_with("pl_full", market=None)


@pytest.mark.asyncio
async def test_spotify_get_playlist_items_tool():
    """Test spotify_get_playlist_items tool output formatting."""
    mock_res = {
        "items": [
            {
                "added_at": "2026-08-01T00:00:00Z",
                "track": {
                    "id": "t1",
                    "name": "One More Time",
                    "artists": [{"name": "Daft Punk"}],
                    "album": {"name": "Discovery"},
                    "duration_ms": 320000,
                    "popularity": 90,
                    "uri": "spotify:track:t1",
                    "is_local": False,
                },
            }
        ]
    }

    with patch("src.tools.playlists.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_playlist_items = AsyncMock(return_value=mock_res)
        mock_get_client.return_value = mock_client

        output = await spotify_get_playlist_items("pl123", limit=10)
        data = json.loads(output)

        assert len(data) == 1
        assert data[0]["name"] == "One More Time"
        assert data[0]["artists"] == ["Daft Punk"]


@pytest.mark.asyncio
async def test_spotify_add_remove_reorder_replace_tools():
    """Test add, remove, reorder, and replace playlist tracks tools."""
    with patch("src.tools.playlists.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.add_tracks_to_playlist = AsyncMock(return_value={"snapshot_id": "snap_add"})
        mock_client.remove_tracks_from_playlist = AsyncMock(return_value={"snapshot_id": "snap_rem"})
        mock_client.reorder_playlist_tracks = AsyncMock(return_value={"snapshot_id": "snap_reorder"})
        mock_client.replace_playlist_tracks = AsyncMock(return_value={"snapshot_id": "snap_replace"})
        mock_client.update_playlist_details = AsyncMock(return_value={})
        mock_get_client.return_value = mock_client

        # Add tracks (passing bare IDs and URIs)
        add_out = await spotify_add_tracks_to_playlist("pl1", ["track1_id", "spotify:track:track2_id"], position=0)
        add_data = json.loads(add_out)
        assert add_data["status"] == "success"
        assert add_data["added_count"] == 2
        assert add_data["snapshot_id"] == "snap_add"
        mock_client.add_tracks_to_playlist.assert_awaited_with(
            "pl1", uris=["spotify:track:track1_id", "spotify:track:track2_id"], position=0
        )

        # Remove tracks
        rem_out = await spotify_remove_tracks_from_playlist("pl1", ["track1_id"], snapshot_id="snap_add")
        rem_data = json.loads(rem_out)
        assert rem_data["status"] == "success"
        assert rem_data["removed_count"] == 1
        assert rem_data["snapshot_id"] == "snap_rem"
        mock_client.remove_tracks_from_playlist.assert_awaited_with(
            "pl1", uris=["spotify:track:track1_id"], snapshot_id="snap_add"
        )

        # Reorder tracks
        reorder_out = await spotify_reorder_playlist_tracks("pl1", range_start=3, insert_before=0, range_length=2)
        reorder_data = json.loads(reorder_out)
        assert reorder_data["status"] == "success"
        assert reorder_data["range_start"] == 3
        assert reorder_data["snapshot_id"] == "snap_reorder"

        # Replace tracks
        replace_out = await spotify_replace_playlist_tracks("pl1", ["t1", "t2", "t3"])
        replace_data = json.loads(replace_out)
        assert replace_data["status"] == "success"
        assert replace_data["total_tracks"] == 3
        assert replace_data["snapshot_id"] == "snap_replace"
        mock_client.replace_playlist_tracks.assert_awaited_with(
            "pl1", uris=["spotify:track:t1", "spotify:track:t2", "spotify:track:t3"]
        )

        # Update details
        upd_out = await spotify_update_playlist_details("pl1", name="Updated Title", public=True)
        upd_data = json.loads(upd_out)
        assert upd_data["status"] == "success"
        assert upd_data["updated_fields"]["name"] == "Updated Title"
        assert upd_data["updated_fields"]["public"] is True


@pytest.mark.asyncio
async def test_spotify_upload_playlist_cover_tool():
    """Test spotify_upload_playlist_cover tool with temporary test file."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        sample_bytes = b"valid_jpeg_payload"
        tmp.write(sample_bytes)
        tmp_path = tmp.name

    try:
        with patch("src.tools.playlists.get_spotify_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.upload_playlist_cover_image = AsyncMock(return_value={})
            mock_get_client.return_value = mock_client

            output = await spotify_upload_playlist_cover("spotify:playlist:pl_cov", image_path=tmp_path)
            data = json.loads(output)

            assert data["status"] == "success"
            assert data["playlist_id"] == "pl_cov"
            mock_client.upload_playlist_cover_image.assert_awaited_once_with(
                "pl_cov",
                base64_image_data=base64.b64encode(sample_bytes).decode("utf-8"),
            )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# --- MCP Ambient Resource Test ---

@pytest.mark.asyncio
async def test_get_playlist_resource():
    """Test get_playlist_resource ambient MCP resource."""
    with patch("src.mcp_server.spotify_get_playlist", new_callable=AsyncMock) as mock_get_pl:
        mock_get_pl.return_value = '{"id": "pl_ambient", "name": "Ambient Soundscapes"}'

        res = await get_playlist_resource("pl_ambient")
        assert "Ambient Soundscapes" in res
        mock_get_pl.assert_awaited_once_with("pl_ambient")
