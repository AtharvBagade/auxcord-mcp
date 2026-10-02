"""Unit tests for SpotifyClient and user tools."""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.client import SpotifyClient
from src.tools.users import spotify_get_user_profile


@pytest.mark.asyncio
async def test_get_user_profile_parsing():
    """Test SpotifyClient.get_user_profile metadata formatting."""
    mock_auth_manager = MagicMock()
    mock_auth_manager.get_valid_access_token.return_value = "mock_token"

    client = SpotifyClient(auth_manager=mock_auth_manager)

    mock_api_response = {
        "id": "test_user_id",
        "display_name": "Test User",
        "email": "test@example.com",
        "product": "premium",
        "country": "US",
        "followers": {"total": 42},
        "uri": "spotify:user:test_user_id",
        "external_urls": {"spotify": "https://open.spotify.com/user/test_user_id"},
        "images": [{"url": "https://example.com/avatar.jpg"}],
    }

    with patch.object(client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_api_response
        profile = await client.get_user_profile()

        assert profile["id"] == "test_user_id"
        assert profile["display_name"] == "Test User"
        assert profile["email"] == "test@example.com"
        assert profile["product"] == "premium"
        assert profile["followers"] == 42
        assert profile["image_url"] == "https://example.com/avatar.jpg"
        mock_request.assert_called_once_with("GET", "/me")


@pytest.mark.asyncio
async def test_spotify_get_user_profile_tool():
    """Test spotify_get_user_profile MCP tool function output."""
    mock_profile = {
        "id": "mcp_user",
        "display_name": "MCP User",
        "product": "premium",
    }
    with patch("src.tools.users.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_user_profile = AsyncMock(return_value=mock_profile)
        mock_get_client.return_value = mock_client

        tool_output = await spotify_get_user_profile()
        parsed_output = json.loads(tool_output)

        assert parsed_output["id"] == "mcp_user"
        assert parsed_output["display_name"] == "MCP User"
        assert parsed_output["product"] == "premium"


@pytest.mark.asyncio
async def test_client_player_methods():
    """Test client-level player, devices, and queue request construction."""
    client = SpotifyClient(auth_manager=MagicMock())

    with patch.object(client, "request", new_callable=AsyncMock) as mock_req:
        mock_req.return_value = {}

        # get_playback_state
        await client.get_playback_state(market="US")
        mock_req.assert_awaited_with("GET", "/me/player", params={"market": "US"})

        # get_currently_playing
        await client.get_currently_playing(market="GB")
        mock_req.assert_awaited_with("GET", "/me/player/currently-playing", params={"market": "GB"})

        # get_available_devices
        await client.get_available_devices()
        mock_req.assert_awaited_with("GET", "/me/player/devices")

        # transfer_playback
        await client.transfer_playback(device_id="dev1", play=True)
        mock_req.assert_awaited_with("PUT", "/me/player", json_data={"device_ids": ["dev1"], "play": True}, expect_json=False)

        # play with context
        await client.play(device_id="dev1", context_uri="spotify:album:1", position_ms=5000)
        mock_req.assert_awaited_with(
            "PUT",
            "/me/player/play",
            params={"device_id": "dev1"},
            json_data={"context_uri": "spotify:album:1", "position_ms": 5000},
            expect_json=False,
        )

        # pause
        await client.pause(device_id="dev1")
        mock_req.assert_awaited_with("PUT", "/me/player/pause", params={"device_id": "dev1"}, expect_json=False)

        # next & prev
        await client.skip_to_next(device_id="dev1")
        mock_req.assert_awaited_with("POST", "/me/player/next", params={"device_id": "dev1"}, expect_json=False)

        await client.skip_to_previous()
        mock_req.assert_awaited_with("POST", "/me/player/previous", params=None, expect_json=False)

        # seek & volume
        await client.seek_to_position(position_ms=10000, device_id="dev1")
        mock_req.assert_awaited_with("PUT", "/me/player/seek", params={"position_ms": 10000, "device_id": "dev1"}, expect_json=False)

        await client.set_volume(volume_percent=70, device_id="dev1")
        mock_req.assert_awaited_with("PUT", "/me/player/volume", params={"volume_percent": 70, "device_id": "dev1"}, expect_json=False)

        # shuffle & repeat
        await client.toggle_shuffle(state=True, device_id="dev1")
        mock_req.assert_awaited_with("PUT", "/me/player/shuffle", params={"state": "true", "device_id": "dev1"}, expect_json=False)

        await client.set_repeat_mode(state="track", device_id="dev1")
        mock_req.assert_awaited_with("PUT", "/me/player/repeat", params={"state": "track", "device_id": "dev1"}, expect_json=False)

        # queue
        await client.get_queue()
        mock_req.assert_awaited_with("GET", "/me/player/queue")

        await client.add_to_queue(uri="spotify:track:123", device_id="dev1")
        mock_req.assert_awaited_with("POST", "/me/player/queue", params={"uri": "spotify:track:123", "device_id": "dev1"}, expect_json=False)


@pytest.mark.asyncio
async def test_client_empty_and_no_content_responses():
    """Test SpotifyClient.request handles empty bodies and 204 No Content without JSONDecodeError."""
    mock_auth_manager = MagicMock()
    mock_auth_manager.get_valid_access_token.return_value = "mock_token"

    mock_http = AsyncMock()
    # Mock response with 204 and empty content
    resp_204 = MagicMock()
    resp_204.status_code = 204
    resp_204.content = b""
    resp_204.text = ""
    resp_204.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

    # Mock response with 200 and whitespace / empty text
    resp_200_empty = MagicMock()
    resp_200_empty.status_code = 200
    resp_200_empty.content = b"  "
    resp_200_empty.text = "  "
    resp_200_empty.json.side_effect = json.JSONDecodeError("Expecting value", "  ", 0)

    mock_http.request = AsyncMock(side_effect=[resp_204, resp_200_empty])

    client = SpotifyClient(auth_manager=mock_auth_manager, http_client=mock_http)

    res1 = await client.request("PUT", "/me/player/repeat", params={"state": "track"})
    assert res1 == {}

    res2 = await client.request("PUT", "/me/player/shuffle", params={"state": "true"})
    assert res2 == {}


def _non_json_200() -> MagicMock:
    """A 200 OK whose body is non-empty plain text, as Spotify returns for some player commands."""
    resp = MagicMock()
    resp.status_code = 200
    resp.text = "1a2b3c4d5e"
    resp.content = resp.text.encode()
    resp.raise_for_status.return_value = None
    resp.json.side_effect = json.JSONDecodeError("Extra data", resp.text, 1)
    return resp


@pytest.mark.asyncio
async def test_request_skips_json_parsing_when_not_expected():
    """request(expect_json=False) returns {} for a non-JSON 2xx body instead of raising."""
    mock_auth_manager = MagicMock()
    mock_auth_manager.get_valid_access_token.return_value = "mock_token"
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=_non_json_200())

    client = SpotifyClient(auth_manager=mock_auth_manager, http_client=mock_http)

    assert await client.request("PUT", "/me/player/pause", expect_json=False) == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method, kwargs",
    [
        ("pause", {}),
        ("skip_to_next", {}),
        ("skip_to_previous", {}),
        ("seek_to_position", {"position_ms": 30000}),
        ("toggle_shuffle", {"state": True}),
        ("set_repeat_mode", {"state": "track"}),
        ("add_to_queue", {"uri": "spotify:track:123"}),
        ("play", {}),
        ("set_volume", {"volume_percent": 50}),
        ("transfer_playback", {"device_id": "dev1"}),
    ],
)
async def test_player_commands_tolerate_non_json_success_body(method, kwargs):
    """BUG-1: player commands must not fail when Spotify returns 200 with a non-JSON body."""
    mock_auth_manager = MagicMock()
    mock_auth_manager.get_valid_access_token.return_value = "mock_token"
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=_non_json_200())

    client = SpotifyClient(auth_manager=mock_auth_manager, http_client=mock_http)

    assert await getattr(client, method)(**kwargs) == {}


# --- Hook A: source-level Spotify API error logging ------------------------


def _make_401_free_response(status_code: int, text: str = "") -> MagicMock:
    """Build a MagicMock httpx.Response-like object that isn't a 401."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.content = text.encode()
    return resp


@pytest.mark.asyncio
async def test_request_logs_http_status_error(caplog):
    """Hook A logs a verbose ERROR block on httpx.HTTPStatusError and re-raises."""
    mock_auth_manager = MagicMock()
    mock_auth_manager.get_valid_access_token.return_value = "mock_token"

    resp = _make_401_free_response(404, text='{"error": {"status": 404, "message": "Device not found"}}')
    http_request = httpx.Request("PUT", "https://api.spotify.com/v1/me/player/play")
    real_response = httpx.Response(404, request=http_request, text=resp.text)
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404 error", request=http_request, response=real_response
    )
    resp.status_code = 404

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=resp)

    client = SpotifyClient(auth_manager=mock_auth_manager, http_client=mock_http)

    with caplog.at_level(logging.ERROR, logger="auxcord"):
        with pytest.raises(httpx.HTTPStatusError):
            await client.request("PUT", "/me/player/play", params={"device_id": None})

    assert any(
        "SPOTIFY_API_FAILURE" in record.message
        and "PUT" in record.message
        and "/me/player/play" in record.message
        and "404" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_request_logs_network_error(caplog):
    """Hook A logs a verbose ERROR block on network/timeout failures and re-raises."""
    mock_auth_manager = MagicMock()
    mock_auth_manager.get_valid_access_token.return_value = "mock_token"

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(side_effect=httpx.ConnectTimeout("connection timed out"))

    client = SpotifyClient(auth_manager=mock_auth_manager, http_client=mock_http)

    with caplog.at_level(logging.ERROR, logger="auxcord"):
        with pytest.raises(httpx.ConnectTimeout):
            await client.request("GET", "/me")

    assert any(
        "SPOTIFY_API_FAILURE" in record.message and "status=N/A" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_request_logs_json_parse_error(caplog):
    """Hook A logs a verbose ERROR block on an invalid JSON body and raises ValueError."""
    mock_auth_manager = MagicMock()
    mock_auth_manager.get_valid_access_token.return_value = "mock_token"

    resp = MagicMock()
    resp.status_code = 200
    resp.text = "not json"
    resp.content = b"not json"
    resp.raise_for_status.return_value = None
    resp.json.side_effect = json.JSONDecodeError("Expecting value", "not json", 0)

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=resp)

    client = SpotifyClient(auth_manager=mock_auth_manager, http_client=mock_http)

    with caplog.at_level(logging.ERROR, logger="auxcord"):
        with pytest.raises(ValueError, match="Invalid JSON response"):
            await client.request("GET", "/me")

    assert any("SPOTIFY_API_FAILURE" in record.message and "JSON parse error" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_request_no_error_log_on_success(caplog):
    """Hook A does not log an ERROR when the request succeeds."""
    mock_auth_manager = MagicMock()
    mock_auth_manager.get_valid_access_token.return_value = "mock_token"

    resp = MagicMock()
    resp.status_code = 200
    resp.text = '{"id": "abc"}'
    resp.content = resp.text.encode()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"id": "abc"}

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=resp)

    client = SpotifyClient(auth_manager=mock_auth_manager, http_client=mock_http)

    with caplog.at_level(logging.ERROR, logger="auxcord"):
        result = await client.request("GET", "/me")

    assert result == {"id": "abc"}
    assert not any("SPOTIFY_API_FAILURE" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_request_401_retry_path_unaffected():
    """The existing 401-retry-then-succeed path still works with hook A wrapping request()."""
    mock_auth_manager = MagicMock()
    mock_auth_manager.get_valid_access_token.return_value = "old_token"
    mock_auth_manager.load_token_cache.return_value = {"refresh_token": "refresh123"}
    mock_auth_manager.refresh_access_token = MagicMock()

    resp_401 = MagicMock()
    resp_401.status_code = 401
    resp_401.text = "Unauthorized"
    resp_401.content = b"Unauthorized"

    resp_ok = MagicMock()
    resp_ok.status_code = 200
    resp_ok.text = '{"id": "abc"}'
    resp_ok.content = resp_ok.text.encode()
    resp_ok.raise_for_status.return_value = None
    resp_ok.json.return_value = {"id": "abc"}

    # After refresh, get_valid_access_token should return the new token.
    mock_auth_manager.get_valid_access_token.side_effect = ["old_token", "new_token"]

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(side_effect=[resp_401, resp_ok])

    client = SpotifyClient(auth_manager=mock_auth_manager, http_client=mock_http)

    result = await client.request("GET", "/me")

    assert result == {"id": "abc"}
    mock_auth_manager.refresh_access_token.assert_called_once_with("refresh123")
    assert mock_http.request.await_count == 2

