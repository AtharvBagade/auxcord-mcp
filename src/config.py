"""Configuration settings for Spotify MCP Server."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Full set of OAuth scopes required for Spotify MCP Server features
DEFAULT_SPOTIFY_SCOPES: list[str] = [
    "user-read-private",
    "user-read-email",
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-public",
    "playlist-modify-private",
    "user-library-read",
    "user-library-modify",
    "user-top-read",
    "user-read-recently-played",
    "user-follow-read",
    "user-follow-modify",
]


class SpotifySettings(BaseSettings):
    """Configuration options loaded from environment variables or .env file."""

    spotify_client_id: str = Field(
        default="",
        description="Spotify App Client ID from Spotify Developer Dashboard",
    )
    spotify_client_secret: str | None = Field(
        default=None,
        description="Optional Spotify App Client Secret",
    )
    spotify_redirect_uri: str = Field(
        default="http://127.0.0.1:8888/callback",
        description="OAuth 2.0 Redirect URI",
    )
    spotify_token_cache_path: str = Field(
        default=".spotify_token.json",
        description="Path to store cached OAuth user access and refresh tokens",
    )
    mcp_server_name: str = Field(
        default="Spotify MCP Server",
        description="Display name for the MCP server",
    )
    mcp_host: str = Field(
        default="127.0.0.1",
        description="Host to bind the HTTP transport to",
    )
    mcp_port: int = Field(
        default=8000,
        description="Port to bind the HTTP transport to",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level for spotify_mcp logger (e.g. DEBUG, INFO, WARNING). "
        "Full tracebacks on tool failures only print at DEBUG.",
    )
    scopes: list[str] = Field(
        default_factory=lambda: DEFAULT_SPOTIFY_SCOPES,
        description="OAuth scopes required for full Spotify features",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def load_settings() -> SpotifySettings:
    """Load and return SpotifySettings configuration."""
    return SpotifySettings()
