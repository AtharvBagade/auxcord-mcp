"""Unit and integration tests for real-time playback, devices, queue, and player MCP resources."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.mcp_server import (
    get_player_current_resource,
    get_player_queue_resource,
)
from src.tools.devices import (
    spotify_get_available_devices,
    spotify_transfer_playback,
)
from src.tools.playback import (
    spotify_get_currently_playing,
    spotify_get_playback_state,
    spotify_pause,
    spotify_play,
    spotify_seek_to_position,
    spotify_set_repeat_mode,
    spotify_set_volume,
    spotify_skip_to_next,
    spotify_skip_to_previous,
    spotify_toggle_shuffle,
)
from src.tools.queue import (
    spotify_add_to_queue,
    spotify_get_queue,
)


@pytest.mark.asyncio
async def test_spotify_play_resume():
    """Test resuming playback without specific context or tracks."""
    with patch("src.tools.playback.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.play = AsyncMock(return_value={})
        mock_get_client.return_value = mock_client

        res = await spotify_play()
        data = json.loads(res)

        assert data["status"] == "success"
        mock_client.play.assert_awaited_once_with(
            device_id=None,
            context_uri=None,
            uris=None,
            offset=None,
            position_ms=None,
        )


@pytest.mark.asyncio
async def test_spotify_play_context_with_offset():
    """Test starting playback of a playlist with track offset position."""
    with patch("src.tools.playback.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.play = AsyncMock(return_value={})
        mock_get_client.return_value = mock_client

        res = await spotify_play(
            context_uri="spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
            offset_position=3,
            position_ms=15000,
        )
        data = json.loads(res)

        assert data["status"] == "success"
        mock_client.play.assert_awaited_once_with(
            device_id=None,
            context_uri="spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
            uris=None,
            offset={"position": 3},
            position_ms=15000,
        )


@pytest.mark.asyncio
async def test_spotify_play_uris_with_offset_uri():
    """Test playing specific track list with offset URI."""
    with patch("src.tools.playback.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.play = AsyncMock(return_value={})
        mock_get_client.return_value = mock_client

        res = await spotify_play(
            uris=["spotify:track:t1", "spotify:track:t2"],
            offset_uri="spotify:track:t2",
        )
        data = json.loads(res)

        assert data["status"] == "success"
        mock_client.play.assert_awaited_once_with(
            device_id=None,
            context_uri=None,
            uris=["spotify:track:t1", "spotify:track:t2"],
            offset={"uri": "spotify:track:t2"},
            position_ms=None,
        )


@pytest.mark.asyncio
async def test_spotify_play_no_active_device_recovery():
    """Test self-healing JSON response on 404 No Active Device error (ADR-0001)."""
    with patch("src.tools.playback.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response = httpx.Response(
            status_code=404,
            request=httpx.Request("PUT", "https://api.spotify.com/v1/me/player/play"),
        )
        mock_client.play = AsyncMock(side_effect=httpx.HTTPStatusError("No device", request=mock_response.request, response=mock_response))
        mock_get_client.return_value = mock_client

        res = await spotify_play()
        data = json.loads(res)

        assert data["status"] == "error"
        assert data["error_code"] == "NO_ACTIVE_DEVICE"
        assert "spotify_get_available_devices" in data["message"]


@pytest.mark.asyncio
async def test_spotify_play_restriction_violated():
    """Test structured response when account lacks Premium (403)."""
    with patch("src.tools.playback.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_response = httpx.Response(
            status_code=403,
            request=httpx.Request("PUT", "https://api.spotify.com/v1/me/player/play"),
        )
        mock_client.play = AsyncMock(side_effect=httpx.HTTPStatusError("Forbidden", request=mock_response.request, response=mock_response))
        mock_get_client.return_value = mock_client

        res = await spotify_play()
        data = json.loads(res)

        assert data["status"] == "error"
        assert data["error_code"] == "RESTRICTION_VIOLATED"


@pytest.mark.asyncio
async def test_playback_controls_pause_next_previous():
    """Test pause, skip_to_next, and skip_to_previous tools."""
    with patch("src.tools.playback.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.pause = AsyncMock(return_value={})
        mock_client.skip_to_next = AsyncMock(return_value={})
        mock_client.skip_to_previous = AsyncMock(return_value={})
        mock_get_client.return_value = mock_client

        res_pause = await spotify_pause(device_id="d1")
        res_next = await spotify_skip_to_next()
        res_prev = await spotify_skip_to_previous()

        assert json.loads(res_pause)["status"] == "success"
        assert json.loads(res_next)["status"] == "success"
        assert json.loads(res_prev)["status"] == "success"

        mock_client.pause.assert_awaited_once_with(device_id="d1")
        mock_client.skip_to_next.assert_awaited_once_with(device_id=None)
        mock_client.skip_to_previous.assert_awaited_once_with(device_id=None)


@pytest.mark.asyncio
async def test_control_tools_report_success_on_non_json_200_body():
    """BUG-1: a 200 with a non-JSON body from Spotify must surface as success, not EXECUTION_ERROR."""
    from src.client import SpotifyClient

    resp = MagicMock()
    resp.status_code = 200
    resp.text = "1a2b3c4d5e"
    resp.content = resp.text.encode()
    resp.raise_for_status.return_value = None
    resp.json.side_effect = json.JSONDecodeError("Extra data", resp.text, 1)

    mock_auth_manager = MagicMock()
    mock_auth_manager.get_valid_access_token.return_value = "mock_token"
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=resp)
    client = SpotifyClient(auth_manager=mock_auth_manager, http_client=mock_http)

    with (
        patch("src.tools.playback.get_spotify_client", return_value=client),
        patch("src.tools.queue.get_spotify_client", return_value=client),
    ):
        results = [
            await spotify_pause(),
            await spotify_skip_to_next(),
            await spotify_skip_to_previous(),
            await spotify_seek_to_position(30000),
            await spotify_toggle_shuffle(True),
            await spotify_set_repeat_mode("track"),
            await spotify_add_to_queue("spotify:track:123"),
        ]

    for res in results:
        assert json.loads(res)["status"] == "success", res
    # Each command hits Spotify exactly once -- no retry, no duplicate side effects.
    assert mock_http.request.await_count == len(results)


@pytest.mark.asyncio
async def test_playback_controls_seek_volume_shuffle_repeat():
    """Test seek, volume, shuffle, and repeat mode tools."""
    with patch("src.tools.playback.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.seek_to_position = AsyncMock(return_value={})
        mock_client.set_volume = AsyncMock(return_value={})
        mock_client.toggle_shuffle = AsyncMock(return_value={})
        mock_client.set_repeat_mode = AsyncMock(return_value={})
        mock_get_client.return_value = mock_client

        # Seek
        res_seek = await spotify_seek_to_position(45000)
        assert json.loads(res_seek)["status"] == "success"
        mock_client.seek_to_position.assert_awaited_once_with(position_ms=45000, device_id=None)

        # Volume valid & invalid
        res_vol = await spotify_set_volume(80)
        assert json.loads(res_vol)["status"] == "success"

        res_vol_invalid = await spotify_set_volume(150)
        assert json.loads(res_vol_invalid)["status"] == "error"
        assert json.loads(res_vol_invalid)["error_code"] == "INVALID_ARGUMENT"

        # Shuffle
        res_shuff = await spotify_toggle_shuffle(True)
        assert json.loads(res_shuff)["status"] == "success"

        # Repeat valid & invalid
        res_rep = await spotify_set_repeat_mode("context")
        assert json.loads(res_rep)["status"] == "success"

        res_rep_invalid = await spotify_set_repeat_mode("invalid_mode")
        assert json.loads(res_rep_invalid)["status"] == "error"
        assert json.loads(res_rep_invalid)["error_code"] == "INVALID_ARGUMENT"


@pytest.mark.asyncio
async def test_spotify_get_playback_state_and_currently_playing():
    """Test get_playback_state and get_currently_playing with pruned high-signal data (ADR-0002)."""
    mock_raw_state = {
        "is_playing": True,
        "progress_ms": 35000,
        "shuffle_state": True,
        "repeat_state": "track",
        "currently_playing_type": "track",
        "device": {
            "id": "dev1",
            "name": "MacBook Pro",
            "type": "Computer",
            "is_active": True,
            "volume_percent": 75,
        },
        "item": {
            "id": "t1",
            "name": "Blinding Lights",
            "artists": [{"name": "The Weeknd"}],
            "album": {"name": "After Hours", "available_markets": ["US", "GB", "DE"]},
            "duration_ms": 200000,
            "uri": "spotify:track:t1",
            "available_markets": ["US", "GB", "CA", "DE", "FR"],
        },
        "context": {
            "type": "album",
            "uri": "spotify:album:a1",
        },
    }

    with patch("src.tools.playback.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_playback_state = AsyncMock(return_value=mock_raw_state)
        mock_client.get_currently_playing = AsyncMock(return_value=mock_raw_state)
        mock_get_client.return_value = mock_client

        # Playback state
        state_output = await spotify_get_playback_state()
        state_data = json.loads(state_output)

        assert state_data["is_playing"] is True
        assert state_data["progress_ms"] == 35000
        assert state_data["item"]["name"] == "Blinding Lights"
        assert "available_markets" not in state_data["item"]  # High-signal pruned
        assert "popularity" not in state_data["item"]  # Removed by Spotify
        assert state_data["device"]["name"] == "MacBook Pro"

        # Currently playing
        curr_output = await spotify_get_currently_playing()
        curr_data = json.loads(curr_output)

        assert curr_data["is_playing"] is True
        assert curr_data["item"]["name"] == "Blinding Lights"


@pytest.mark.asyncio
async def test_spotify_get_playback_state_empty():
    """Test get_playback_state when no session is active."""
    with patch("src.tools.playback.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_playback_state = AsyncMock(return_value={})
        mock_client.get_currently_playing = AsyncMock(return_value={})
        mock_get_client.return_value = mock_client

        state_output = await spotify_get_playback_state()
        state_data = json.loads(state_output)
        assert state_data["is_playing"] is False
        assert state_data["item"] is None

        curr_output = await spotify_get_currently_playing()
        curr_data = json.loads(curr_output)
        assert curr_data["is_playing"] is False


@pytest.mark.asyncio
async def test_devices_tools():
    """Test available devices listing and playback transfer."""
    mock_devices = {
        "devices": [
            {
                "id": "dev1",
                "name": "Living Room Speaker",
                "type": "Speaker",
                "is_active": False,
                "volume_percent": 50,
            },
            {
                "id": "dev2",
                "name": "iPhone",
                "type": "Smartphone",
                "is_active": True,
                "volume_percent": 90,
            },
        ]
    }

    with patch("src.tools.devices.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_available_devices = AsyncMock(return_value=mock_devices)
        mock_client.transfer_playback = AsyncMock(return_value={})
        mock_get_client.return_value = mock_client

        # Get devices
        devices_out = await spotify_get_available_devices()
        dev_list = json.loads(devices_out)
        assert len(dev_list) == 2
        assert dev_list[0]["name"] == "Living Room Speaker"
        assert dev_list[1]["is_active"] is True

        # Transfer playback
        transfer_out = await spotify_transfer_playback(device_id="dev1", play=True)
        transfer_data = json.loads(transfer_out)
        assert transfer_data["status"] == "success"
        mock_client.transfer_playback.assert_awaited_once_with(device_id="dev1", play=True)


@pytest.mark.asyncio
async def test_queue_tools():
    """Test queue inspection and adding tracks to queue."""
    mock_queue_resp = {
        "currently_playing": {
            "id": "t1",
            "name": "Current Song",
            "artists": [{"name": "Artist 1"}],
            "album": {"name": "Album 1"},
            "duration_ms": 180000,
            "uri": "spotify:track:t1",
            "available_markets": ["US"],
        },
        "queue": [
            {
                "id": "t2",
                "name": "Next Song",
                "artists": [{"name": "Artist 2"}],
                "album": {"name": "Album 2"},
                "duration_ms": 210000,
                "uri": "spotify:track:t2",
                "available_markets": ["US"],
            }
        ],
    }

    with patch("src.tools.queue.get_spotify_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_queue = AsyncMock(return_value=mock_queue_resp)
        mock_client.add_to_queue = AsyncMock(return_value={})
        mock_get_client.return_value = mock_client

        # Get queue
        q_out = await spotify_get_queue()
        q_data = json.loads(q_out)
        assert q_data["currently_playing"]["name"] == "Current Song"
        assert len(q_data["queue"]) == 1
        assert q_data["queue"][0]["name"] == "Next Song"
        assert "available_markets" not in q_data["queue"][0]

        # Add to queue with full URI
        add_out = await spotify_add_to_queue("spotify:track:t2")
        assert json.loads(add_out)["status"] == "success"
        mock_client.add_to_queue.assert_awaited_once_with(uri="spotify:track:t2", device_id=None)

        # Add to queue with raw 22-char ID (auto prefix)
        add_raw = await spotify_add_to_queue("4cOdK2wGLETKBW3PvgPWqT")
        assert json.loads(add_raw)["status"] == "success"
        assert "spotify:track:4cOdK2wGLETKBW3PvgPWqT" in json.loads(add_raw)["message"]

        # Add invalid URI
        add_inv = await spotify_add_to_queue("invalid_uri_string")
        assert json.loads(add_inv)["status"] == "error"
        assert json.loads(add_inv)["error_code"] == "INVALID_URI"


@pytest.mark.asyncio
async def test_mcp_player_ambient_resources():
    """Test player and queue ambient MCP resources."""
    with patch("src.mcp_server.spotify_get_playback_state", new_callable=AsyncMock) as mock_state, \
         patch("src.mcp_server.spotify_get_queue", new_callable=AsyncMock) as mock_queue:

        mock_state.return_value = '{"is_playing": true, "item": {"name": "Song A"}}'
        mock_queue.return_value = '{"queue": [{"name": "Song B"}]}'

        res_curr = await get_player_current_resource()
        res_q = await get_player_queue_resource()

        assert "Song A" in res_curr
        assert "Song B" in res_q
