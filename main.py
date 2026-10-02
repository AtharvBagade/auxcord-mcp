#!/usr/bin/env python3
"""Spotify MCP Server entrypoint launcher."""

import sys
import argparse
from rich.console import Console
from rich.panel import Panel

from src.config import load_settings
from src.lib.logger import set_transport_mode
from src.mcp_server import mcp

console = Console()


def display_header():
    """Render Spotify MCP Server banner header."""
    header_text = (
        "[bold green]Spotify MCP Server[/bold green] - [bold cyan]Model Context Protocol Gateway[/bold cyan]\n"
        "[dim]Exposing Spotify playback, queue, playlists, recommendations, and search to AI agents[/dim]"
    )
    console.print(Panel(header_text, border_style="green", expand=False))


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Spotify MCP Server Launcher")
    parser.add_argument(
        "--stdio",
        action="store_true",
        help="Run FastMCP server in STDIO mode for Claude Desktop / Cursor integration",
    )
    args = parser.parse_args()

    if args.stdio:
        set_transport_mode("stdio")
        mcp.run(transport="stdio")
    else:
        set_transport_mode("http")
        display_header()
        settings = load_settings()
        console.print(f"[bold white]Server Name:[/bold white] {settings.mcp_server_name}")
        console.print(f"[bold white]Redirect URI:[/bold white] {settings.spotify_redirect_uri}")
        console.print("[dim]Run with --stdio to launch MCP server transport for LLM clients.[/dim]")


if __name__ == "__main__":
    main()
