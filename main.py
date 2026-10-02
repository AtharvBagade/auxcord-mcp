#!/usr/bin/env python3
"""Spotify MCP Server entrypoint launcher."""

import argparse

from src.config import load_settings
from src.lib.logger import set_transport_mode
from src.mcp_server import mcp


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Spotify MCP Server Launcher")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="MCP transport to serve on (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Host to bind the HTTP transport to (default: settings.mcp_host)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind the HTTP transport to (default: settings.mcp_port)",
    )
    args = parser.parse_args()

    set_transport_mode(args.transport)

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        settings = load_settings()
        mcp.run(
            transport="http",
            host=args.host or settings.mcp_host,
            port=args.port or settings.mcp_port,
            stateless_http=True,
        )


if __name__ == "__main__":
    main()
