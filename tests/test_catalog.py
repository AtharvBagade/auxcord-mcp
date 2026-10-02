"""Unit tests for catalog search and metadata tools."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.tools.catalog import (
    spotify_get_album,
    spotify_get_artist,
    spotify_search_catalog,
)

# Fields Spotify removed from track/artist/album objects (live-verified; Feb 2026 Web API changes).
REMOVED_ARTIST_FIELDS = {"genres", "popularity", "followers"}


@pytest.mark.asyncio
async def test_spotify_search_catalog():
    """Test spotify_search_catalog tool parsing."""
    mock_search_response = {
        "tracks": {
            "items": [
                {
                    "id": "t1",
                    "name": "Get Lucky",
                    "artists": [{"name": "Daft Punk"}],
                    "album": {"name": "Random Access Memories"},
                    "duration_ms": 240000,
                    "uri": "spotify:track:t1",
                }
            ]
        },
        "artists": {
            "items": [
                {
                    "id": "a1",
                    "name": "Daft Punk",
                    "uri": "spotify:artist:a1",
                }
            ]
        },
        "playlists": {
            "items": [
                None,
                {
                    "id": "p1",
                    "name": "Daft Punk Essentials",
                    "owner": {"display_name": "Spotify"},
                    "items": {"href": "https://api.spotify.com/v1/playlists/p1/items", "total": 31},
                    "uri": "spotify:playlist:p1",
                },
            ]
        },
    }

    with patch("src.tools.catalog.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.search_catalog = AsyncMock(return_value=mock_search_response)
        mock_get_client.return_value = mock_client

        output = await spotify_search_catalog("Daft Punk")
        data = json.loads(output)

        assert "tracks" in data
        assert data["tracks"][0]["name"] == "Get Lucky"
        assert data["tracks"][0]["artists"] == ["Daft Punk"]
        assert "artists" in data
        assert data["artists"][0]["name"] == "Daft Punk"
        assert "popularity" not in data["tracks"][0]
        assert not REMOVED_ARTIST_FIELDS & data["artists"][0].keys()
        assert data["playlists"] == [
            {
                "id": "p1",
                "name": "Daft Punk Essentials",
                "owner": "Spotify",
                "tracks_total": 31,
                "uri": "spotify:playlist:p1",
            }
        ]


@pytest.mark.asyncio
async def test_spotify_get_artist():
    """Test spotify_get_artist tool parsing."""
    mock_artist_response = {
        "id": "a1",
        "name": "Daft Punk",
        "uri": "spotify:artist:a1",
        "external_urls": {"spotify": "https://open.spotify.com/artist/a1"},
        "images": [{"url": "https://example.com/daftpunk.jpg"}],
    }

    with patch("src.tools.catalog.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_artist = AsyncMock(return_value=mock_artist_response)
        mock_get_client.return_value = mock_client

        output = await spotify_get_artist("a1")
        data = json.loads(output)

        assert data["id"] == "a1"
        assert data["name"] == "Daft Punk"
        assert not REMOVED_ARTIST_FIELDS & data.keys()
        assert data["image_url"] == "https://example.com/daftpunk.jpg"


def test_artist_top_tracks_tool_removed():
    """GET /artists/{id}/top-tracks returns 403 since Feb 2026; the tool and client method are gone."""
    from src import mcp_server as server
    from src.client import SpotifyClient
    from src.tools import catalog

    assert not hasattr(catalog, "spotify_get_artist_top_tracks")
    assert not hasattr(server, "spotify_get_artist_top_tracks")
    assert not hasattr(SpotifyClient, "get_artist_top_tracks")


@pytest.mark.asyncio
async def test_spotify_get_album():
    """Test spotify_get_album tool parsing."""
    mock_album_response = {
        "id": "alb1",
        "name": "Discovery",
        "album_type": "album",
        "artists": [{"name": "Daft Punk"}],
        "release_date": "2001-03-12",
        "total_tracks": 14,
        "uri": "spotify:album:alb1",
        "tracks": {
            "items": [
                {
                    "id": "t1",
                    "track_number": 1,
                    "name": "One More Time",
                    "duration_ms": 320000,
                    "artists": [{"name": "Daft Punk"}],
                    "uri": "spotify:track:t1",
                }
            ]
        },
    }

    with patch("src.tools.catalog.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_album = AsyncMock(return_value=mock_album_response)
        mock_get_client.return_value = mock_client

        output = await spotify_get_album("alb1")
        data = json.loads(output)

        assert data["id"] == "alb1"
        assert data["name"] == "Discovery"
        assert data["total_tracks"] == 14
        assert len(data["tracks"]) == 1
        assert data["tracks"][0]["name"] == "One More Time"
        assert not {"label", "popularity"} & data.keys()
