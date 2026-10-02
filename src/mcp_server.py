"""FastMCP Server initialization, tool registration, and ambient resources for Spotify MCP Server."""

from fastmcp import FastMCP
from src.config import load_settings
from src.tools.users import (
    spotify_get_user_profile,
    spotify_get_top_tracks,
    spotify_get_top_artists,
    spotify_get_recently_played,
    spotify_get_saved_tracks,
)
from src.tools.catalog import (
    spotify_search_catalog,
    spotify_get_artist,
    spotify_get_artist_top_tracks,
    spotify_get_album,
)
from src.tools.playback import (
    spotify_play,
    spotify_pause,
    spotify_skip_to_next,
    spotify_skip_to_previous,
    spotify_seek_to_position,
    spotify_set_volume,
    spotify_toggle_shuffle,
    spotify_set_repeat_mode,
    spotify_get_playback_state,
    spotify_get_currently_playing,
)
from src.tools.devices import (
    spotify_get_available_devices,
    spotify_transfer_playback,
)
from src.tools.queue import (
    spotify_get_queue,
    spotify_add_to_queue,
)
from src.tools.playlists import (
    spotify_create_playlist,
    spotify_get_user_playlists,
    spotify_get_playlist,
    spotify_get_playlist_items,
    spotify_add_tracks_to_playlist,
    spotify_remove_tracks_from_playlist,
    spotify_reorder_playlist_tracks,
    spotify_replace_playlist_tracks,
    spotify_update_playlist_details,
    spotify_upload_playlist_cover,
)

settings = load_settings()

# Initialize FastMCP Server
mcp = FastMCP(name=settings.mcp_server_name)

# Register Modular Tools - Users & Library
mcp.add_tool(spotify_get_user_profile)
mcp.add_tool(spotify_get_top_tracks)
mcp.add_tool(spotify_get_top_artists)
mcp.add_tool(spotify_get_recently_played)
mcp.add_tool(spotify_get_saved_tracks)

# Register Modular Tools - Catalog Search & Metadata
mcp.add_tool(spotify_search_catalog)
mcp.add_tool(spotify_get_artist)
mcp.add_tool(spotify_get_artist_top_tracks)
mcp.add_tool(spotify_get_album)

# Register Modular Tools - Playback Control & Player State
mcp.add_tool(spotify_play)
mcp.add_tool(spotify_pause)
mcp.add_tool(spotify_skip_to_next)
mcp.add_tool(spotify_skip_to_previous)
mcp.add_tool(spotify_seek_to_position)
mcp.add_tool(spotify_set_volume)
mcp.add_tool(spotify_toggle_shuffle)
mcp.add_tool(spotify_set_repeat_mode)
mcp.add_tool(spotify_get_playback_state)
mcp.add_tool(spotify_get_currently_playing)

# Register Modular Tools - Devices
mcp.add_tool(spotify_get_available_devices)
mcp.add_tool(spotify_transfer_playback)

# Register Modular Tools - Queue
mcp.add_tool(spotify_get_queue)
mcp.add_tool(spotify_add_to_queue)

# Register Modular Tools - Playlist Management & Curation
mcp.add_tool(spotify_create_playlist)
mcp.add_tool(spotify_get_user_playlists)
mcp.add_tool(spotify_get_playlist)
mcp.add_tool(spotify_get_playlist_items)
mcp.add_tool(spotify_add_tracks_to_playlist)
mcp.add_tool(spotify_remove_tracks_from_playlist)
mcp.add_tool(spotify_reorder_playlist_tracks)
mcp.add_tool(spotify_replace_playlist_tracks)
mcp.add_tool(spotify_update_playlist_details)
mcp.add_tool(spotify_upload_playlist_cover)


# Ambient MCP Resources - User Context
@mcp.resource("spotify://user/profile")
async def get_user_profile_resource() -> str:
    """User profile metadata and product subscription context."""
    return await spotify_get_user_profile()


@mcp.resource("spotify://user/top-tracks")
async def get_user_top_tracks_resource() -> str:
    """Top listened tracks summary context for current user."""
    return await spotify_get_top_tracks(time_range="medium_term", limit=20)


@mcp.resource("spotify://user/top-artists")
async def get_user_top_artists_resource() -> str:
    """Top listened artists summary context for current user."""
    return await spotify_get_top_artists(time_range="medium_term", limit=20)


# Ambient MCP Resources - Player & Queue Context
@mcp.resource("spotify://player/current")
async def get_player_current_resource() -> str:
    """Real-time active player state and currently playing track context."""
    return await spotify_get_playback_state()


@mcp.resource("spotify://player/queue")
async def get_player_queue_resource() -> str:
    """Live snapshot of user's playback queue context."""
    return await spotify_get_queue()


# Ambient MCP Resources - Playlist Context
@mcp.resource("spotify://playlist/{playlist_id}")
async def get_playlist_resource(playlist_id: str) -> str:
    """Full tracklist and metadata snapshot context for a specific playlist."""
    return await spotify_get_playlist(playlist_id)


def run_server():
    """Run the FastMCP server via STDIO transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()

