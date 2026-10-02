"""Settings must load the project's .env regardless of the working directory."""

from pathlib import Path

from src.config import SpotifySettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_env_file_is_anchored_to_project_root():
    """MCP clients (Cursor, Codex, Antigravity, Claude Desktop) often launch the server from
    another working directory; a cwd-relative `.env` would silently drop the credentials."""
    env_file = Path(SpotifySettings.model_config["env_file"])
    assert env_file.is_absolute()
    assert env_file == PROJECT_ROOT / ".env"


def test_settings_load_from_project_env_when_cwd_differs(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text('SPOTIFY_CLIENT_ID="from-project-env"\n')
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.chdir("/")

    settings = SpotifySettings(_env_file=env_file)

    assert settings.spotify_client_id == "from-project-env"
