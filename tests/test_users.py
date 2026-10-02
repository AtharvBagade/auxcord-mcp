"""Unit tests for user library, personalization, and MCP resources."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mcp_server import (
    get_user_profile_resource,
    get_user_top_artists_resource,
    get_user_top_tracks_resource,
)
from src.tools.users import (
    spotify_get_recently_played,
    spotify_get_saved_tracks,
    spotify_get_top_artists,
    spotify_get_top_tracks,
)


@pytest.mark.asyncio
async def test_spotify_get_top_tracks():
    """Test spotify_get_top_tracks tool."""
    mock_tracks_response = {
        "items": [
            {
                "id": "t1",
                "name": "Starboy",
                "artists": [{"name": "The Weeknd"}],
                "album": {"name": "Starboy"},
                "duration_ms": 230000,
                "uri": "spotify:track:t1",
            }
        ]
    }

    with patch("src.tools.users.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_top_tracks = AsyncMock(return_value=mock_tracks_response)
        mock_get_client.return_value = mock_client

        output = await spotify_get_top_tracks(time_range="short_term", limit=10)
        data = json.loads(output)

        assert len(data) == 1
        assert data[0]["name"] == "Starboy"
        assert data[0]["artists"] == ["The Weeknd"]
        assert "popularity" not in data[0]


@pytest.mark.asyncio
async def test_spotify_get_top_artists():
    """Test spotify_get_top_artists tool."""
    mock_artists_response = {
        "items": [
            {
                "id": "a1",
                "name": "The Weeknd",
                "uri": "spotify:artist:a1",
            }
        ]
    }

    with patch("src.tools.users.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_top_artists = AsyncMock(return_value=mock_artists_response)
        mock_get_client.return_value = mock_client

        output = await spotify_get_top_artists(time_range="medium_term", limit=10)
        data = json.loads(output)

        assert len(data) == 1
        assert data[0]["name"] == "The Weeknd"
        assert not {"genres", "popularity", "followers"} & data[0].keys()


@pytest.mark.asyncio
async def test_spotify_get_recently_played():
    """Test spotify_get_recently_played tool."""
    mock_recent_response = {
        "items": [
            {
                "played_at": "2026-07-31T12:00:00Z",
                "track": {
                    "id": "t1",
                    "name": "Blinding Lights",
                    "artists": [{"name": "The Weeknd"}],
                    "album": {"name": "After Hours"},
                    "uri": "spotify:track:t1",
                },
            }
        ]
    }

    with patch("src.tools.users.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_recently_played = AsyncMock(return_value=mock_recent_response)
        mock_get_client.return_value = mock_client

        output = await spotify_get_recently_played(limit=5)
        data = json.loads(output)

        assert len(data) == 1
        assert data[0]["played_at"] == "2026-07-31T12:00:00Z"
        assert data[0]["track_name"] == "Blinding Lights"


@pytest.mark.asyncio
async def test_spotify_get_saved_tracks():
    """Test spotify_get_saved_tracks tool."""
    mock_saved_response = {
        "items": [
            {
                "added_at": "2026-07-30T10:00:00Z",
                "track": {
                    "id": "t1",
                    "name": "Save Your Tears",
                    "artists": [{"name": "The Weeknd"}],
                    "album": {"name": "After Hours"},
                    "uri": "spotify:track:t1",
                },
            }
        ]
    }

    with patch("src.tools.users.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_saved_tracks = AsyncMock(return_value=mock_saved_response)
        mock_get_client.return_value = mock_client

        output = await spotify_get_saved_tracks(limit=10)
        data = json.loads(output)

        assert len(data) == 1
        assert data[0]["track_name"] == "Save Your Tears"
        assert "popularity" not in data[0]


@pytest.mark.asyncio
async def test_mcp_resources():
    """Test MCP ambient resource callbacks."""
    with patch("src.mcp_server.spotify_get_user_profile", new_callable=AsyncMock) as mock_prof, \
         patch("src.mcp_server.spotify_get_top_tracks", new_callable=AsyncMock) as mock_tracks, \
         patch("src.mcp_server.spotify_get_top_artists", new_callable=AsyncMock) as mock_artists:

        mock_prof.return_value = '{"id": "user1"}'
        mock_tracks.return_value = '[{"name": "track1"}]'
        mock_artists.return_value = '[{"name": "artist1"}]'

        res_prof = await get_user_profile_resource()
        res_tracks = await get_user_top_tracks_resource()
        res_artists = await get_user_top_artists_resource()

        assert "user1" in res_prof
        assert "track1" in res_tracks
        assert "artist1" in res_artists
