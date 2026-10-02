# Spotify MCP Server

An open-source **Model Context Protocol (MCP) Server** exposing the Spotify Web API directly to AI assistants (Claude Desktop, Cursor, Antigravity, and autonomous LLM agents).

---

## 🚦 Implementation Status & Feature Roadmap

Here is an overview of what is **currently implemented** versus what is **in the pipeline (planned)**.

### ✅ Already Implemented

| Category | Component / Tool / Resource | Status | Description |
| :--- | :--- | :---: | :--- |
| **Authentication & Core** | **OAuth 2.0 PKCE Flow** | ✅ Live | Automatic local callback server (`http://127.0.0.1:8888/callback`), token caching (`.spotify_token.json`), and auto-refresh. |
| | **HTTP Library Layer** | ✅ Live | Async (`HTTPClient`) & sync (`SyncHTTPClient`) connection-pooled clients with error handling and retry logic. |
| **Playback Control** | `spotify_play` | ✅ Live | Start/resume playback (supports `context_uri`, `uris`, `offset`, `position_ms`). |
| | `spotify_pause` | ✅ Live | Pause active playback. |
| | `spotify_skip_to_next` | ✅ Live | Skip to the next track. |
| | `spotify_skip_to_previous` | ✅ Live | Skip to the previous track. |
| | `spotify_seek_to_position` | ✅ Live | Seek to specific position in milliseconds. |
| | `spotify_set_volume` | ✅ Live | Set volume level (0–100%). |
| | `spotify_toggle_shuffle` | ✅ Live | Toggle shuffle mode on/off. |
| | `spotify_set_repeat_mode` | ✅ Live | Set repeat mode (`off`, `track`, `context`). |
| | `spotify_get_playback_state` | ✅ Live | Inspect active device, progress, shuffle/repeat state. |
| | `spotify_get_currently_playing` | ✅ Live | Fetch high-signal metadata of currently playing track/episode. |
| **Device Management** | `spotify_get_available_devices` | ✅ Live | List connected Spotify Connect devices (desktop, mobile, speaker). |
| | `spotify_transfer_playback` | ✅ Live | Transfer playback session to a target `device_id`. |
| **Queue Control** | `spotify_get_queue` | ✅ Live | Inspect current active playback queue. |
| | `spotify_add_to_queue` | ✅ Live | Append track or episode URI to the user's queue. |
| **Catalog & Search** | `spotify_search_catalog` | ✅ Live | Search across tracks, artists, albums, playlists, shows, audiobooks. |
| | `spotify_get_artist` | ✅ Live | Fetch artist name, URI, Spotify URL, and image. |
| | `spotify_get_album` | ✅ Live | Get album details and track listings. |
| **User & Library** | `spotify_get_user_profile` | ✅ Live | Fetch user profile info and subscription tier (Premium/Free). |
| | `spotify_get_top_tracks` | ✅ Live | Fetch user's top listened tracks over selectable time ranges. |
| | `spotify_get_top_artists` | ✅ Live | Fetch user's top listened artists over selectable time ranges. |
| | `spotify_get_recently_played` | ✅ Live | Fetch recent listening history with timestamps. |
| | `spotify_get_saved_tracks` | ✅ Live | Inspect user's saved/liked tracks library. |
| **Ambient MCP Resources** | `spotify://user/profile` | ✅ Live | Ambient user profile & subscription tier context. |
| | `spotify://user/top-tracks` | ✅ Live | Ambient top tracks listening context. |
| | `spotify://user/top-artists` | ✅ Live | Ambient top artists taste profile context. |
| | `spotify://player/current` | ✅ Live | Real-time active player state, device, and track metadata. |
| | `spotify://player/queue` | ✅ Live | Real-time snapshot of the playback queue. |

---

### ⏳ In the Pipeline (Roadmap)

The following capabilities are scheduled across upcoming milestones:

- **🚩 Milestone 4: Full Playlist Management & Custom Cover Art**
  - [ ] `spotify_create_playlist` (Create playlists with title & description; visibility must be set in the Spotify app)
  - [ ] `spotify_get_user_playlists` (List user's created and followed playlists)
  - [ ] `spotify_get_playlist` & `spotify_get_playlist_items` (Retrieve playlist tracks and metadata)
  - [ ] `spotify_add_tracks_to_playlist` & `spotify_remove_tracks_from_playlist` (Manage tracklist)
  - [ ] `spotify_reorder_playlist_tracks` (Reorder tracks for BPM/energy flow)
  - [ ] `spotify_update_playlist_details` (Edit name, description, collaborative status)
  - [ ] `spotify_upload_playlist_cover` (Upload custom base64 JPEG cover art)
  - [ ] Ambient Resource: `spotify://playlist/{playlist_id}`

- **🚩 Milestone 5: Audio Features, Recommendations & Multi-Step Prompts**
  - [ ] `spotify_get_audio_features` & `spotify_get_audio_analysis` (Acoustic metrics: BPM, key, valence, energy, danceability)
  - [ ] `spotify_get_recommendations` (Multi-target acoustic recommendation engine with genre/artist/track seeds)
  - [ ] `spotify_get_available_genre_seeds` (List available recommendation genre seeds)
  - [ ] **MCP Prompts**:
    - `create_mood_playlist`: Translate natural language moods into acoustic targets & playlists.
    - `smart_queue_dj`: Auto-queue tracks matching current listening vibe.
    - `listening_dna_report`: Deep acoustic breakdown of user taste profile.
    - `playlist_cleaner_and_organizer`: Re-sort playlists by harmonic key and energy.

- **🚩 Milestone 6: Multi-Transport Packaging & Client Configurations**
  - [ ] STDIO and HTTP/SSE transport modes.
  - [ ] Pre-packaged configuration templates for **Claude Desktop**, **Cursor**, and **Antigravity**.
  - [ ] End-to-end integration test suite and PyPI distribution package.

---

## ⚠️ Known Spotify API Limitations

These are Spotify-side behaviours, not bugs in this server. Each was confirmed against the live Web API or Spotify's changelog.

- **Playlist visibility can't be set through the API.** Spotify accepts `public: false` on create (`POST /me/playlists`) and update (`PUT /playlists/{id}`) with a `2xx`, but the playlist stays public. The create response even echoes `public: false`. Name and description updates apply normally. For this reason `spotify_create_playlist` and `spotify_update_playlist_details` don't offer a `public` parameter. Set visibility in the Spotify app. ([community thread](https://community.spotify.com/t5/Spotify-for-Developers/Api-to-create-a-private-playlist-doesn-t-work/m-p/6030637/highlight/true))
- **Playlist contents are only available for playlists you own or collaborate on.** For other playlists, `GET /playlists/{id}` returns metadata only (no `items`) and `GET /playlists/{id}/items` returns `403`. `spotify_get_playlist` returns the metadata with an explanatory `note`, and `spotify_get_playlist_items` returns a `PLAYLIST_CONTENTS_UNAVAILABLE` error.
- **Artist and track metadata is reduced.** Spotify no longer returns `genres`, `popularity` or `followers` on artists, `popularity` on tracks, or `label` / `popularity` on albums, so the tools don't either. `GET /artists/{id}/top-tracks` now returns `403` and has no replacement, so there is no artist top-tracks tool. Use `spotify_search_catalog` with `artist:"Name"` instead. ([changelog](https://developer.spotify.com/documentation/web-api/references/changes/february-2026))
- **Playlist track counts can lag.** Right after tracks are added, `GET /me/playlists` may still report the old `items.total`, so `tracks_total` from `spotify_get_user_playlists` can be stale. `spotify_get_playlist` reports the current count.

---

## 🔑 Spotify Developer Setup (Client ID & Secret)

To use this MCP server, you need to register a free developer application with Spotify to obtain your **Client ID** and **Client Secret**. Follow the steps below:

### Step 1: Open the Spotify Developer Dashboard
1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
2. Log in with your standard Spotify account.

### Step 2: Create a New Application
1. Click the **"Create app"** button in the top right.
2. Fill out the application details:
   - **App name**: e.g., `Spotify MCP Server` (or any name you prefer).
   - **App description**: e.g., `MCP Server bridging Spotify API with AI assistants`.
   - **Redirect URIs**: Enter `http://127.0.0.1:8888/callback` and click **Add**.
     > ⚠️ **Important**: The redirect URI must match `http://127.0.0.1:8888/callback` exactly (including the port and path).
   - **Which API/SDKs are you planning to use?**: Select/check **Web API**.
3. Check the checkbox agreeing to the Spotify Developer Terms of Service and click **Save**.

### Step 3: Copy Your Client ID & Client Secret
1. On your newly created app page, click **Settings** (top right) or go to the **Basic Information** tab.
2. You will see your **Client ID**. Copy it.
3. Click **"View client secret"** to reveal your **Client Secret**. Copy it.

### Step 4: (Optional) Add User Accounts in Development Mode
By default, Spotify developer apps start in **Development Mode**:
- Your own Spotify account (the app creator) is automatically authorized.
- If you want other Spotify accounts to use your app, go to **Settings** > **User Management** and add their Spotify email addresses.

---

## ⚙️ Environment Configuration

1. Create a `.env` file in the root of the project (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```

2. Add your credentials into `.env`:
   ```env
   SPOTIFY_CLIENT_ID="your_spotify_client_id_here"
   SPOTIFY_CLIENT_SECRET="your_spotify_client_secret_here"
   SPOTIFY_REDIRECT_URI="http://127.0.0.1:8888/callback"

   # Optional Settings
   SPOTIFY_TOKEN_CACHE_PATH=".spotify_token.json"
   MCP_SERVER_NAME="Spotify MCP Server"
   ```

---

## 🚀 Installation & Running

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies (including development dependencies)
pip install -e ".[dev]"

# 3. Run the MCP server entrypoint
python3 main.py
```

On your first run or when authorization is needed:
- A browser window will automatically open asking you to log into Spotify and authorize the requested permissions.
- The local server on port `8888` will capture the OAuth callback and save the cached tokens to `.spotify_token.json`.
- Subsequent runs will automatically reuse and refresh the token in the background.

---

## 🧪 Testing

Run the test suite using `pytest`:

```bash
pytest
```

---

## 📖 Specifications & Architecture

- [PRD.md](PRD.md): Full product requirements document, API endpoint mapping, and milestone breakdowns.
- [CONTEXT.md](CONTEXT.md): Domain language, high-signal resource representations, and error recovery definitions.
