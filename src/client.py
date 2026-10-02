"""Async Spotify API Client wrapper."""

import json
from typing import Any

from src.auth import SpotifyAuthManager
from src.config import load_settings
from src.lib.http import HTTPClient, get_http_client

SPOTIFY_API_BASE_URL = "https://api.spotify.com/v1"


class SpotifyClient:
    """High-level async client for communicating with Spotify Web API."""

    def __init__(
        self,
        auth_manager: SpotifyAuthManager | None = None,
        http_client: HTTPClient | None = None,
    ):
        self.auth_manager = auth_manager or SpotifyAuthManager(load_settings())
        self._http_client = http_client

    @property
    def http_client(self) -> HTTPClient:
        if self._http_client is None:
            self._http_client = get_http_client()
        return self._http_client

    async def get_headers(self) -> dict[str, str]:
        access_token = self.auth_manager.get_valid_access_token()
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    async def request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: Any | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated async request to the Spotify Web API."""
        url = f"{SPOTIFY_API_BASE_URL}{endpoint}" if endpoint.startswith("/") else f"{SPOTIFY_API_BASE_URL}/{endpoint}"
        access_token = self.auth_manager.get_valid_access_token()
        req_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        if headers:
            req_headers.update(headers)

        response = await self.http_client.request(
            method=method.upper(),
            url=url,
            headers=req_headers,
            params=params,
            json=json_data,
            data=data,
        )

        # Retry once on 401 Unauthorized by forcing a token refresh
        if response.status_code == 401:
            token_data = self.auth_manager.load_token_cache()
            if token_data and "refresh_token" in token_data:
                self.auth_manager.refresh_access_token(token_data["refresh_token"])
                new_token = self.auth_manager.get_valid_access_token()
                req_headers["Authorization"] = f"Bearer {new_token}"
                response = await self.http_client.request(
                    method=method.upper(),
                    url=url,
                    headers=req_headers,
                    params=params,
                    json=json_data,
                    data=data,
                )

        response.raise_for_status()
        if response.status_code in (202, 204) or not len(response.text):
            return {}
        try:
            return response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            print(f"JSON parse error from Spotify API: {exc}")
            raise ValueError("Invalid JSON response from Spotify API")

    async def get_user_profile(self) -> dict[str, Any]:
        """Fetch current authenticated user's profile details (`GET /v1/me`)."""
        raw_data = await self.request("GET", "/me")
        images = raw_data.get("images", [])
        image_url = images[0]["url"] if images else None

        return {
            "id": raw_data.get("id"),
            "display_name": raw_data.get("display_name"),
            "email": raw_data.get("email"),
            "product": raw_data.get("product"),
            "country": raw_data.get("country"),
            "followers": raw_data.get("followers", {}).get("total", 0),
            "uri": raw_data.get("uri"),
            "profile_url": raw_data.get("external_urls", {}).get("spotify"),
            "image_url": image_url,
        }

    async def search_catalog(
        self,
        query: str,
        search_types: list[str] | None = None,
        limit: int = 10,
        offset: int = 0,
        market: str | None = None,
    ) -> dict[str, Any]:
        """Search Spotify catalog across tracks, artists, albums, playlists, etc. (`GET /v1/search`)."""
        if search_types is None:
            search_types = ["track", "artist", "album"]
        type_str = ",".join(search_types)

        params: dict[str, Any] = {
            "q": query,
            "type": type_str,
            "limit": limit,
            "offset": offset,
        }
        if market:
            params["market"] = market

        return await self.request("GET", "/search", params=params)

    async def get_artist(self, artist_id: str) -> dict[str, Any]:
        """Fetch artist metadata (`GET /v1/artists/{id}`)."""
        return await self.request("GET", f"/artists/{artist_id}")

    async def get_artist_top_tracks(self, artist_id: str, market: str = "US") -> dict[str, Any]:
        """Fetch top 10 tracks for an artist (`GET /v1/artists/{id}/top-tracks`)."""
        return await self.request("GET", f"/artists/{artist_id}/top-tracks", params={"market": market})

    async def get_album(self, album_id: str) -> dict[str, Any]:
        """Fetch album details and tracklist (`GET /v1/albums/{id}`)."""
        return await self.request("GET", f"/albums/{album_id}")

    async def get_top_artists(
        self, time_range: str = "medium_term", limit: int = 20, offset: int = 0
    ) -> dict[str, Any]:
        """Fetch user's top artists (`GET /v1/me/top/artists`)."""
        params = {"time_range": time_range, "limit": limit, "offset": offset}
        return await self.request("GET", "/me/top/artists", params=params)

    async def get_top_tracks(
        self, time_range: str = "medium_term", limit: int = 20, offset: int = 0
    ) -> dict[str, Any]:
        """Fetch user's top tracks (`GET /v1/me/top/tracks`)."""
        params = {"time_range": time_range, "limit": limit, "offset": offset}
        return await self.request("GET", "/me/top/tracks", params=params)

    async def get_recently_played(self, limit: int = 20) -> dict[str, Any]:
        """Fetch user's recently played tracks (`GET /v1/me/player/recently-played`)."""
        return await self.request("GET", "/me/player/recently-played", params={"limit": limit})

    async def get_saved_tracks(self, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """Fetch user's saved ("Liked Songs") tracks (`GET /v1/me/tracks`)."""
        return await self.request("GET", "/me/tracks", params={"limit": limit, "offset": offset})

    async def get_playback_state(self, market: str | None = None) -> dict[str, Any]:
        """Fetch current playback state including active device, progress, and track (`GET /v1/me/player`)."""
        params = {"market": market} if market else None
        return await self.request("GET", "/me/player", params=params)

    async def get_currently_playing(self, market: str | None = None) -> dict[str, Any]:
        """Fetch currently playing track/episode metadata (`GET /v1/me/player/currently-playing`)."""
        params = {"market": market} if market else None
        return await self.request("GET", "/me/player/currently-playing", params=params)

    async def get_available_devices(self) -> dict[str, Any]:
        """Fetch user's available connected Spotify Connect devices (`GET /v1/me/player/devices`)."""
        return await self.request("GET", "/me/player/devices")

    async def transfer_playback(self, device_id: str, play: bool = False) -> dict[str, Any]:
        """Transfer playback to a specified device (`PUT /v1/me/player`)."""
        payload = {"device_ids": [device_id], "play": play}
        return await self.request("PUT", "/me/player", json_data=payload)

    async def play(
        self,
        device_id: str | None = None,
        context_uri: str | None = None,
        uris: list[str] | None = None,
        offset: dict[str, Any] | None = None,
        position_ms: int | None = None,
    ) -> dict[str, Any]:
        """Start or resume playback (`PUT /v1/me/player/play`)."""
        params = {"device_id": device_id} if device_id else None
        payload: dict[str, Any] = {}
        if context_uri:
            payload["context_uri"] = context_uri
        elif uris:
            payload["uris"] = uris

        if offset:
            payload["offset"] = offset
        if position_ms is not None:
            payload["position_ms"] = position_ms

        return await self.request(
            "PUT",
            "/me/player/play",
            params=params,
            json_data=payload if payload else None,
        )

    async def pause(self, device_id: str | None = None) -> dict[str, Any]:
        """Pause playback on active device (`PUT /v1/me/player/pause`)."""
        params = {"device_id": device_id} if device_id else None
        return await self.request("PUT", "/me/player/pause", params=params)

    async def skip_to_next(self, device_id: str | None = None) -> dict[str, Any]:
        """Skip to next track in queue/context (`POST /v1/me/player/next`)."""
        params = {"device_id": device_id} if device_id else None
        return await self.request("POST", "/me/player/next", params=params)

    async def skip_to_previous(self, device_id: str | None = None) -> dict[str, Any]:
        """Skip to previous track (`POST /v1/me/player/previous`)."""
        params = {"device_id": device_id} if device_id else None
        return await self.request("POST", "/me/player/previous", params=params)

    async def seek_to_position(self, position_ms: int, device_id: str | None = None) -> dict[str, Any]:
        """Seek to position in milliseconds on active device (`PUT /v1/me/player/seek`)."""
        params: dict[str, Any] = {"position_ms": position_ms}
        if device_id:
            params["device_id"] = device_id
        return await self.request("PUT", "/me/player/seek", params=params)

    async def set_volume(self, volume_percent: int, device_id: str | None = None) -> dict[str, Any]:
        """Set volume percentage (0-100) on active device (`PUT /v1/me/player/volume`)."""
        params: dict[str, Any] = {"volume_percent": volume_percent}
        if device_id:
            params["device_id"] = device_id
        return await self.request("PUT", "/me/player/volume", params=params)

    async def toggle_shuffle(self, state: bool, device_id: str | None = None) -> dict[str, Any]:
        """Toggle shuffle on/off (`PUT /v1/me/player/shuffle`)."""
        params: dict[str, Any] = {"state": "true" if state else "false"}
        if device_id:
            params["device_id"] = device_id
        return await self.request("PUT", "/me/player/shuffle", params=params)

    async def set_repeat_mode(self, state: str, device_id: str | None = None) -> dict[str, Any]:
        """Set repeat mode ('off', 'track', 'context') (`PUT /v1/me/player/repeat`)."""
        params: dict[str, Any] = {"state": state}
        if device_id:
            params["device_id"] = device_id
        return await self.request("PUT", "/me/player/repeat", params=params)

    async def get_queue(self) -> dict[str, Any]:
        """Fetch user's current playback queue (`GET /v1/me/player/queue`)."""
        return await self.request("GET", "/me/player/queue")

    async def add_to_queue(self, uri: str, device_id: str | None = None) -> dict[str, Any]:
        """Append track or episode URI to the playback queue (`POST /v1/me/player/queue`)."""
        params: dict[str, Any] = {"uri": uri}
        if device_id:
            params["device_id"] = device_id
        return await self.request("POST", "/me/player/queue", params=params)

    # --- Playlist Management Methods ---

    async def create_playlist(
        self,
        name: str,
        description: str = "",
        public: bool = True,
        collaborative: bool = False,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a playlist for a user (`POST /v1/users/{user_id}/playlists`)."""
        if not user_id:
            profile = await self.get_user_profile()
            user_id = profile["id"]

        payload: dict[str, Any] = {
            "name": name,
            "description": description,
            "public": public,
            "collaborative": collaborative,
        }
        return await self.request("POST", f"/users/{user_id}/playlists", json_data=payload)

    async def get_user_playlists(self, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        """Fetch user's playlists (`GET /v1/me/playlists`)."""
        params = {"limit": limit, "offset": offset}
        return await self.request("GET", "/me/playlists", params=params)

    async def get_playlist(
        self,
        playlist_id: str,
        market: str | None = None,
        fields: str | None = None,
    ) -> dict[str, Any]:
        """Fetch playlist metadata and tracks (`GET /v1/playlists/{playlist_id}`)."""
        params: dict[str, Any] = {}
        if market:
            params["market"] = market
        if fields:
            params["fields"] = fields
        return await self.request("GET", f"/playlists/{playlist_id}", params=params or None)

    async def get_playlist_items(
        self,
        playlist_id: str,
        limit: int = 50,
        offset: int = 0,
        market: str | None = None,
        fields: str | None = None,
    ) -> dict[str, Any]:
        """Fetch items of a playlist (`GET /v1/playlists/{playlist_id}/tracks`)."""
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if market:
            params["market"] = market
        if fields:
            params["fields"] = fields
        return await self.request("GET", f"/playlists/{playlist_id}/tracks", params=params)

    async def add_tracks_to_playlist(
        self,
        playlist_id: str,
        uris: list[str],
        position: int | None = None,
    ) -> dict[str, Any]:
        """Add tracks or episodes to a playlist (`POST /v1/playlists/{playlist_id}/tracks`)."""
        payload: dict[str, Any] = {"uris": uris}
        if position is not None:
            payload["position"] = position
        return await self.request("POST", f"/playlists/{playlist_id}/tracks", json_data=payload)

    async def remove_tracks_from_playlist(
        self,
        playlist_id: str,
        uris: list[str],
        snapshot_id: str | None = None,
    ) -> dict[str, Any]:
        """Remove tracks or episodes from a playlist (`DELETE /v1/playlists/{playlist_id}/tracks`)."""
        payload: dict[str, Any] = {"tracks": [{"uri": uri} for uri in uris]}
        if snapshot_id:
            payload["snapshot_id"] = snapshot_id
        return await self.request("DELETE", f"/playlists/{playlist_id}/tracks", json_data=payload)

    async def reorder_playlist_tracks(
        self,
        playlist_id: str,
        range_start: int,
        insert_before: int,
        range_length: int = 1,
        snapshot_id: str | None = None,
    ) -> dict[str, Any]:
        """Reorder tracks in a playlist (`PUT /v1/playlists/{playlist_id}/tracks`)."""
        payload: dict[str, Any] = {
            "range_start": range_start,
            "insert_before": insert_before,
            "range_length": range_length,
        }
        if snapshot_id:
            payload["snapshot_id"] = snapshot_id
        return await self.request("PUT", f"/playlists/{playlist_id}/tracks", json_data=payload)

    async def replace_playlist_tracks(
        self,
        playlist_id: str,
        uris: list[str],
    ) -> dict[str, Any]:
        """Replace all tracks in a playlist (`PUT /v1/playlists/{playlist_id}/tracks`)."""
        payload = {"uris": uris}
        return await self.request("PUT", f"/playlists/{playlist_id}/tracks", json_data=payload)

    async def update_playlist_details(
        self,
        playlist_id: str,
        name: str | None = None,
        public: bool | None = None,
        collaborative: bool | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Update playlist details (`PUT /v1/playlists/{playlist_id}`)."""
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if public is not None:
            payload["public"] = public
        if collaborative is not None:
            payload["collaborative"] = collaborative
        if description is not None:
            payload["description"] = description
        return await self.request("PUT", f"/playlists/{playlist_id}", json_data=payload)

    async def upload_playlist_cover_image(
        self,
        playlist_id: str,
        base64_image_data: str,
    ) -> dict[str, Any]:
        """Upload custom JPEG cover image to a playlist (`PUT /v1/playlists/{playlist_id}/images`)."""
        return await self.request(
            "PUT",
            f"/playlists/{playlist_id}/images",
            headers={"Content-Type": "image/jpeg"},
            data=base64_image_data,
        )





# Global singleton instance
_spotify_client_instance: SpotifyClient | None = None


def get_spotify_client() -> SpotifyClient:
    """Get or create singleton SpotifyClient instance."""
    global _spotify_client_instance
    if _spotify_client_instance is None:
        _spotify_client_instance = SpotifyClient()
    return _spotify_client_instance
