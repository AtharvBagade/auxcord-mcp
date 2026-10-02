# Auxcord

**Hand your AI the aux.** An MCP server for Spotify.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![MCP](https://img.shields.io/badge/MCP-stdio%20%7C%20streamable%20HTTP-green)
![Version](https://img.shields.io/badge/version-0.1.0-lightgrey)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](LICENSE)

Auxcord is a Model Context Protocol (MCP) server that gives AI assistants (Claude Desktop, Cursor, Antigravity, or your own agents) control over Spotify: playback, devices, the queue, search, your library, and playlists.

## Highlights

- **32 tools** covering playback, devices, the queue, catalog search, your listening history and library, and playlist management, including custom cover art.
- **6 ambient resources** (`spotify://...`) that give the assistant context such as what's playing, your queue and your taste profile, without a tool call.
- **Agent-friendly errors.** Failures come back as structured JSON with an `error_code` and recovery guidance (for example, "no active device, call `spotify_get_available_devices`") instead of raw HTTP errors. Invalid arguments are rejected before reaching Spotify.
- **Compact responses.** Spotify payloads are trimmed to the fields an assistant actually needs, so they use less of its context window.
- **Works locally or over HTTP.** It runs over stdio for desktop clients or as a stateless streamable-HTTP server, and handles OAuth 2.0 PKCE login and token refresh for you.

## Overview

The server wraps the [Spotify Web API](https://developer.spotify.com/documentation/web-api) as MCP tools and resources. An assistant connected to it can handle requests like "queue three upbeat Daft Punk tracks", "make a playlist from my top tracks this month" or "move playback to my phone".

It signs in as your own Spotify account, using a Spotify developer app you create (see [Installation](#installation)). Playback control requires Spotify Premium.

### Tools

| Area | Tools |
|---|---|
| Playback | `spotify_play`, `spotify_pause`, `spotify_skip_to_next`, `spotify_skip_to_previous`, `spotify_seek_to_position`, `spotify_set_volume`, `spotify_toggle_shuffle`, `spotify_set_repeat_mode`, `spotify_get_playback_state`, `spotify_get_currently_playing` |
| Devices | `spotify_get_available_devices`, `spotify_transfer_playback` |
| Queue | `spotify_get_queue`, `spotify_add_to_queue` |
| Catalog | `spotify_search_catalog`, `spotify_get_artist`, `spotify_get_album` |
| User and library | `spotify_get_user_profile`, `spotify_get_top_tracks`, `spotify_get_top_artists`, `spotify_get_recently_played`, `spotify_get_saved_tracks` |
| Playlists | `spotify_create_playlist`, `spotify_get_user_playlists`, `spotify_get_playlist`, `spotify_get_playlist_items`, `spotify_add_tracks_to_playlist`, `spotify_remove_tracks_from_playlist`, `spotify_reorder_playlist_tracks`, `spotify_replace_playlist_tracks`, `spotify_update_playlist_details`, `spotify_upload_playlist_cover` |

Resources: `spotify://user/profile`, `spotify://user/top-tracks`, `spotify://user/top-artists`, `spotify://player/current`, `spotify://player/queue`, `spotify://playlist/{playlist_id}`.

### Known Spotify API limitations

These are limits on Spotify's side, not bugs in this server. Each was confirmed against the live Web API or [Spotify's changelog](https://developer.spotify.com/documentation/web-api/references/changes/february-2026).

- **Playlist visibility can't be set through the API.** Spotify accepts `public: false` on create and update, but the playlist stays public. For that reason the playlist tools don't offer a `public` parameter. Set visibility in the Spotify app. ([community thread](https://community.spotify.com/t5/Spotify-for-Developers/Api-to-create-a-private-playlist-doesn-t-work/m-p/6030637/highlight/true))
- **Playlist contents are only available for playlists you own or collaborate on.** For other playlists, `spotify_get_playlist` returns metadata with an explanatory `note`, and `spotify_get_playlist_items` returns a `PLAYLIST_CONTENTS_UNAVAILABLE` error.
- **Artist and track metadata is reduced.** Spotify no longer returns `genres`, `popularity` or `followers` on artists, `popularity` on tracks, or `label` / `popularity` on albums. Artist top tracks are no longer available, so use `spotify_search_catalog` with `artist:"Name"` instead.
- **Search returns at most 10 results per type** (default 5), and `limit + offset` can't exceed 1000.
- **Playlist search hides some results.** Spotify returns some playlist results as `null` (about 3 in 10 in live testing). `spotify_search_catalog` drops them and reports how many it dropped in `playlists_hidden_by_spotify`. If a page comes back mostly or entirely hidden, try the next `offset`.
- **Playlist track counts can lag.** Right after tracks are added, `spotify_get_user_playlists` may report a stale `tracks_total`. `spotify_get_playlist` reports the current count.

## Usage

After [installing](#installation), add the server to your MCP client. Every client launches the same command, `/path/to/auxcord-mcp/.venv/bin/auxcord-mcp`. Replace `/path/to` with where you cloned the repo.

Then restart the client and ask something like *"What's playing right now? Add two similar tracks to my queue."*

### Claude Desktop

Edit `claude_desktop_config.json` (Settings > Developer > Edit Config):

```json
{
  "mcpServers": {
    "auxcord": {
      "command": "/path/to/auxcord-mcp/.venv/bin/auxcord-mcp"
    }
  }
}
```

### Cursor

Edit `~/.cursor/mcp.json` (all projects) or `.cursor/mcp.json` (one project):

```json
{
  "mcpServers": {
    "auxcord": {
      "command": "/path/to/auxcord-mcp/.venv/bin/auxcord-mcp"
    }
  }
}
```

### Codex

Edit `~/.codex/config.toml` (all projects) or `.codex/config.toml` (one project):

```toml
[mcp_servers.auxcord]
command = "/path/to/auxcord-mcp/.venv/bin/auxcord-mcp"
```

### Antigravity

Edit `~/.gemini/antigravity/mcp_config.json` (Agent panel > MCP Servers > Manage MCP Servers > View raw config):

```json
{
  "mcpServers": {
    "auxcord": {
      "command": "/path/to/auxcord-mcp/.venv/bin/auxcord-mcp"
    }
  }
}
```

### Streamable HTTP

To run one server that several clients share, start it over HTTP:

```bash
auxcord-mcp --transport http   # serves http://127.0.0.1:8000/mcp
```

Use `--host` and `--port` to change the address. Then point your client at the URL instead of a command:

| Client | Config |
|---|---|
| Cursor | `"auxcord": { "url": "http://127.0.0.1:8000/mcp" }` |
| Codex | `[mcp_servers.auxcord]` with `url = "http://127.0.0.1:8000/mcp"` |
| Antigravity | `"auxcord": { "serverUrl": "http://127.0.0.1:8000/mcp" }` |

## Installation

You need Python 3.10 or newer and a Spotify account (Premium for playback control).

**1. Create a Spotify developer app**

1. Open the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) and click **Create app**.
2. Add the redirect URI `http://127.0.0.1:8888/callback`. It must match exactly, including the port and path.
3. Under **Which API/SDKs are you planning to use?**, select **Web API**, then save.
4. From the app's **Settings**, copy the **Client ID** and **Client Secret**.

New apps start in Development Mode: your own account works right away, and other accounts must be added under **Settings > User Management**.

**2. Install the server**

```bash
git clone https://github.com/AtharvBagade/auxcord-mcp.git
cd auxcord-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

**3. Configure credentials**

```bash
cp .env.example .env
```

Then fill in `.env`:

```env
SPOTIFY_CLIENT_ID="your_client_id"
SPOTIFY_CLIENT_SECRET="your_client_secret"
SPOTIFY_REDIRECT_URI="http://127.0.0.1:8888/callback"

# Optional (defaults shown)
SPOTIFY_TOKEN_CACHE_PATH=".spotify_token.json"
MCP_SERVER_NAME="Auxcord"
MCP_HOST="127.0.0.1"
MCP_PORT=8000
LOG_LEVEL="INFO"
```

**4. Sign in once**

```bash
python -c "from src.auth import SpotifyAuthManager; from src.config import load_settings; SpotifyAuthManager(load_settings()).get_valid_access_token()"
```

A browser window opens for you to sign in to Spotify. The token is cached in `.spotify_token.json` and refreshed automatically after that. If you skip this step, the same sign-in happens on the first tool call. Logs go to stderr; set `LOG_LEVEL=DEBUG` to include full tracebacks.

## Feedback and Contributing

Bug reports and feature requests are welcome in [GitHub Issues](https://github.com/AtharvBagade/auxcord-mcp/issues). Please include the tool name, its arguments and the `error_code` you got back.

To work on the server, install the development dependencies and run the tests:

```bash
pip install -e ".[dev]"
pytest
ruff check src tests
```
