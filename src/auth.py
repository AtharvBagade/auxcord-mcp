"""Spotify OAuth 2.0 PKCE Authentication Manager."""

import base64
import hashlib
import json
import secrets
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from src.config import SpotifySettings, load_settings
from src.lib.http import get_sync_http_client
from src.lib.logger import logger

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"


def generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE (code_verifier, code_challenge) tuple.
    
    code_verifier: 64-128 chars URL-safe random string.
    code_challenge: Base64URL-encoded SHA256 hash of code_verifier (without padding).
    """
    code_verifier = secrets.token_urlsafe(64)[:128]
    sha256_hash = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = (
        base64.urlsafe_b64encode(sha256_hash).decode("ascii").rstrip("=")
    )
    return code_verifier, code_challenge


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for capturing Spotify OAuth callback redirect."""

    captured_code: str | None = None
    captured_error: str | None = None

    def do_GET(self):
        """Handle incoming OAuth redirect GET request."""
        parsed_url = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_url.query)

        if "code" in query_params:
            OAuthCallbackHandler.captured_code = query_params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            html_response = """
            <!text/html>
            <html>
            <head><title>Spotify Authorization Success</title></head>
            <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                <h1 style="color: #1DB954;">Authorization Successful!</h1>
                <p>Spotify MCP Server has been authenticated successfully.</p>
                <p>You can close this browser tab and return to your application.</p>
            </body>
            </html>
            """
            self.wfile.write(html_response.encode("utf-8"))
        elif "error" in query_params:
            OAuthCallbackHandler.captured_error = query_params["error"][0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            html_response = f"""
            <!text/html>
            <html>
            <head><title>Spotify Authorization Error</title></head>
            <body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
                <h1 style="color: #E91E63;">Authorization Failed</h1>
                <p>Error: {OAuthCallbackHandler.captured_error}</p>
            </body>
            </html>
            """
            self.wfile.write(html_response.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default HTTP server access logs."""


class SpotifyAuthManager:
    """Manages Spotify OAuth 2.0 PKCE authentication flow and token persistence."""

    def __init__(self, settings: SpotifySettings | None = None):
        self.settings = settings or load_settings()
        # Expand user directory (e.g. `~/`) if present
        raw_path = Path(self.settings.spotify_token_cache_path).expanduser()
        # If relative, resolve against project root to prevent Read-only file system errors
        # when spawned by external MCP hosts (like Claude Desktop) with CWD set to `/`
        if not raw_path.is_absolute():
            project_root = Path(__file__).resolve().parent.parent
            raw_path = project_root / raw_path
        self.cache_path = raw_path

    def load_token_cache(self) -> dict[str, Any] | None:
        """Load cached token dictionary from disk if available."""
        if not self.cache_path.exists():
            return None
        try:
            with open(self.cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def save_token_cache(self, token_data: dict[str, Any]) -> None:
        """Save token dictionary to disk."""
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=2)

    def is_token_expired(self, token_data: dict[str, Any], buffer_seconds: int = 60) -> bool:
        """Check if the access token is expired or within safety buffer seconds of expiring."""
        expires_at = token_data.get("expires_at", 0)
        return time.time() + buffer_seconds >= expires_at

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Exchange refresh token for a new access token via Spotify OAuth endpoint."""
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.settings.spotify_client_id,
        }
        if self.settings.spotify_client_secret:
            payload["client_secret"] = self.settings.spotify_client_secret

        client = get_sync_http_client()
        response = client.post(SPOTIFY_TOKEN_URL, data=payload)
        response.raise_for_status()
        data = response.json()

        expires_in = data.get("expires_in", 3600)
        token_data = self.load_token_cache() or {}
        token_data.update({
            "access_token": data["access_token"],
            "expires_in": expires_in,
            "expires_at": int(time.time()) + expires_in,
            "token_type": data.get("token_type", "Bearer"),
        })
        if "refresh_token" in data:
            token_data["refresh_token"] = data["refresh_token"]

        self.save_token_cache(token_data)
        return token_data

    def authenticate(self) -> dict[str, Any]:
        """Perform full interactive OAuth 2.0 PKCE browser authentication flow."""
        if not self.settings.spotify_client_id:
            raise ValueError(
                "SPOTIFY_CLIENT_ID is not configured. Please set it in your .env file."
            )

        code_verifier, code_challenge = generate_pkce_pair()
        parsed_uri = urllib.parse.urlparse(self.settings.spotify_redirect_uri)
        host = parsed_uri.hostname or "127.0.0.1"
        port = parsed_uri.port or 8888

        # Prepare authorization URL
        auth_params = {
            "client_id": self.settings.spotify_client_id,
            "response_type": "code",
            "redirect_uri": self.settings.spotify_redirect_uri,
            "code_challenge_method": "S256",
            "code_challenge": code_challenge,
            "scope": " ".join(self.settings.scopes),
        }
        auth_url = f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

        # Reset handler state
        OAuthCallbackHandler.captured_code = None
        OAuthCallbackHandler.captured_error = None

        # Start HTTP server to listen for single callback
        httpd = HTTPServer((host, port), OAuthCallbackHandler)
        logger.info("Opening browser for Spotify authentication: %s", auth_url)
        webbrowser.open(auth_url)

        # Wait for HTTP request
        while OAuthCallbackHandler.captured_code is None and OAuthCallbackHandler.captured_error is None:
            httpd.handle_request()

        httpd.server_close()

        if OAuthCallbackHandler.captured_error:
            raise RuntimeError(f"Spotify authentication failed: {OAuthCallbackHandler.captured_error}")

        auth_code = OAuthCallbackHandler.captured_code
        if not auth_code:
            raise RuntimeError("Failed to capture Spotify authorization code.")

        # Exchange authorization code for token bundle
        token_payload = {
            "client_id": self.settings.spotify_client_id,
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": self.settings.spotify_redirect_uri,
            "code_verifier": code_verifier,
        }
        if self.settings.spotify_client_secret:
            token_payload["client_secret"] = self.settings.spotify_client_secret

        client = get_sync_http_client()
        response = client.post(SPOTIFY_TOKEN_URL, data=token_payload)
        response.raise_for_status()
        data = response.json()

        expires_in = data.get("expires_in", 3600)
        token_data = {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_in": expires_in,
            "expires_at": int(time.time()) + expires_in,
            "token_type": data.get("token_type", "Bearer"),
            "scope": data.get("scope", ""),
        }
        self.save_token_cache(token_data)
        return token_data

    def get_valid_access_token(self) -> str:
        """Get a valid Spotify access token. Automatically refreshes or triggers PKCE auth if needed."""
        token_data = self.load_token_cache()

        if not token_data or "access_token" not in token_data:
            token_data = self.authenticate()
            return token_data["access_token"]

        if self.is_token_expired(token_data):
            refresh_token_str = token_data.get("refresh_token")
            if refresh_token_str:
                try:
                    token_data = self.refresh_access_token(refresh_token_str)
                    return token_data["access_token"]
                except Exception:
                    # Fallback to fresh authentication if refresh fails
                    token_data = self.authenticate()
                    return token_data["access_token"]
            else:
                token_data = self.authenticate()
                return token_data["access_token"]

        return token_data["access_token"]
