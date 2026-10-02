"""BUG-7/8: client-side argument validation and structured errors for Spotify 400s."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.tools.catalog import spotify_search_catalog
from src.tools.playlists import spotify_get_playlist_items, spotify_get_user_playlists
from src.tools.users import (
    spotify_get_recently_played,
    spotify_get_saved_tracks,
    spotify_get_top_artists,
    spotify_get_top_tracks,
)
from src.tools.validation import structured_bad_request

# (module whose get_spotify_client to patch, tool, kwargs) -- each is rejected by Spotify with a 400 (live-verified).
INVALID_CALLS = [
    ("catalog", spotify_search_catalog, {"query": "x", "limit": 11}),
    ("catalog", spotify_search_catalog, {"query": "x", "limit": 20}),
    ("catalog", spotify_search_catalog, {"query": "x", "limit": 0}),
    ("catalog", spotify_search_catalog, {"query": ""}),
    ("catalog", spotify_search_catalog, {"query": "   "}),
    ("catalog", spotify_search_catalog, {"query": "x", "search_types": ["bogus"]}),
    ("catalog", spotify_search_catalog, {"query": "x", "offset": -1}),
    ("catalog", spotify_search_catalog, {"query": "x", "limit": 10, "offset": 991}),
    ("users", spotify_get_top_tracks, {"time_range": "bogus"}),
    ("users", spotify_get_top_tracks, {"limit": 0}),
    ("users", spotify_get_top_tracks, {"limit": 51}),
    ("users", spotify_get_top_artists, {"time_range": "all_time"}),
    ("users", spotify_get_top_artists, {"limit": 51}),
    ("users", spotify_get_recently_played, {"limit": 0}),
    ("users", spotify_get_recently_played, {"limit": 51}),
    ("users", spotify_get_saved_tracks, {"limit": 51}),
    ("users", spotify_get_saved_tracks, {"offset": -5}),
    ("playlists", spotify_get_user_playlists, {"limit": 51}),
    ("playlists", spotify_get_playlist_items, {"playlist_id": "pl1", "limit": 101}),
    ("playlists", spotify_get_playlist_items, {"playlist_id": "pl1", "limit": 0}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("module, tool, kwargs", INVALID_CALLS)
async def test_invalid_arguments_return_structured_error_without_calling_spotify(module, tool, kwargs):
    with patch(f"src.tools.{module}.get_spotify_client") as mock_get_client:
        data = json.loads(await tool(**kwargs))

    assert data["status"] == "error"
    assert data["error_code"] == "INVALID_ARGUMENT"
    assert data["message"]
    mock_get_client.assert_not_called()


# Boundary values Spotify accepts (live-verified) must still reach the client.
VALID_BOUNDARY_CALLS = [
    ("catalog", spotify_search_catalog, "search_catalog", {"query": "x", "limit": 10, "offset": 990}),
    ("catalog", spotify_search_catalog, "search_catalog", {"query": "x", "limit": 1}),
    ("users", spotify_get_top_tracks, "get_top_tracks", {"time_range": "long_term", "limit": 50}),
    ("users", spotify_get_top_artists, "get_top_artists", {"time_range": "short_term", "limit": 1}),
    ("users", spotify_get_recently_played, "get_recently_played", {"limit": 50}),
    ("users", spotify_get_saved_tracks, "get_saved_tracks", {"limit": 50}),
    ("playlists", spotify_get_user_playlists, "get_user_playlists", {"limit": 50}),
    ("playlists", spotify_get_playlist_items, "get_playlist_items", {"playlist_id": "pl1", "limit": 100}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("module, tool, client_method, kwargs", VALID_BOUNDARY_CALLS)
async def test_boundary_arguments_reach_spotify(module, tool, client_method, kwargs):
    with patch(f"src.tools.{module}.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        setattr(mock_client, client_method, AsyncMock(return_value={}))
        mock_get_client.return_value = mock_client

        await tool(**kwargs)

        getattr(mock_client, client_method).assert_awaited_once()


def _http_error(status: int, text: str) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.spotify.com/v1/search")
    response = httpx.Response(status, request=request, text=text)
    return httpx.HTTPStatusError(f"Client error '{status}'", request=request, response=response)


@pytest.mark.asyncio
async def test_structured_bad_request_maps_spotify_400_to_structured_error():
    """A 400 that slips past validation surfaces Spotify's own message, not a raw httpx error."""

    async def tool(query: str, limit: int = 5) -> str:
        raise _http_error(400, '{"error": {"status": 400, "message": "Invalid limit" } }')

    data = json.loads(await structured_bad_request(tool)(query="x", limit=7))

    assert data == {
        "status": "error",
        "error_code": "SPOTIFY_BAD_REQUEST",
        "message": "Spotify rejected the request: Invalid limit",
    }


@pytest.mark.asyncio
async def test_structured_bad_request_handles_non_json_400_body():
    async def tool() -> str:
        raise _http_error(400, "Bad Request")

    data = json.loads(await structured_bad_request(tool)())
    assert data["error_code"] == "SPOTIFY_BAD_REQUEST"
    assert data["message"] == "Spotify rejected the request: Bad Request"


@pytest.mark.asyncio
async def test_structured_bad_request_leaves_other_errors_alone():
    async def tool() -> str:
        raise _http_error(500, "boom")

    with pytest.raises(httpx.HTTPStatusError):
        await structured_bad_request(tool)()


def test_structured_bad_request_preserves_tool_signature():
    """FastMCP builds the tool schema from the signature, so the wrapper must keep it."""
    import inspect

    async def tool(query: str, limit: int = 5) -> str:
        return ""

    assert inspect.signature(structured_bad_request(tool)) == inspect.signature(tool)
    assert structured_bad_request(tool).__name__ == "tool"


@pytest.mark.asyncio
async def test_registered_tools_return_structured_400():
    """End-to-end through the MCP server: a Spotify 400 from a registered tool is not a raw error."""
    from src.mcp_server import mcp

    with patch("src.tools.users.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_saved_tracks = AsyncMock(
            side_effect=_http_error(400, '{"error": {"status": 400, "message": "Invalid limit" } }')
        )
        mock_get_client.return_value = mock_client

        result = await mcp.call_tool("spotify_get_saved_tracks", {"limit": 10})

    text = result.content[0].text if hasattr(result, "content") else result[0].text
    assert json.loads(text)["error_code"] == "SPOTIFY_BAD_REQUEST"


@pytest.mark.asyncio
async def test_search_default_limit_matches_spotify_default():
    """Spotify's search default is 5 (max 10); omitting limit must not silently request the max."""
    import inspect

    from src.client import SpotifyClient

    assert inspect.signature(spotify_search_catalog).parameters["limit"].default == 5
    assert inspect.signature(SpotifyClient.search_catalog).parameters["limit"].default == 5

    with patch("src.tools.catalog.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.search_catalog = AsyncMock(return_value={})
        mock_get_client.return_value = mock_client

        await spotify_search_catalog("x")

        assert mock_client.search_catalog.await_args.kwargs["limit"] == 5
