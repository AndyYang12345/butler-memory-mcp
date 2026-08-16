"""Command-line entry point: ai-butler-memory-mcp.

``stdio`` serves the Model Context Protocol for DSH's dsh-mcp-client.
``http`` serves the loopback JSON API consumed by the DSH web panel's
host half. Both share one MemoryOperations instance and one principal.
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import sys

import uvicorn

from .config import BridgeConfig
from .mcp_server import StdioMcpServer
from .operations import MemoryOperations
from .tools import build_tools
from . import __version__

from ai_butler_runtime.config import ConfigurationError, load_dotenv
from ai_butler_runtime.persistence.database import Database


def _is_loopback(host: str) -> bool:
    normalized = host.strip().casefold()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized.strip("[]")).is_loopback
    except ValueError:
        return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ai-butler-memory-mcp",
        description="Butler Memory MCP bridge (stdio for agents, http for the panel).",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default="stdio",
        help="stdio speaks MCP to DSH agents; http serves the panel API.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None)
    return parser.parse_args(argv)


def build_operations(config: BridgeConfig) -> MemoryOperations:
    database = Database(config.database)
    return MemoryOperations(
        database, user_id=config.user_id, device_id=config.device_id
    )


def run_stdio(config: BridgeConfig) -> int:
    operations = build_operations(config)
    server = StdioMcpServer(
        server_name="butler-memory",
        server_version=__version__,
        tools=build_tools(operations),
        instructions=(
            "Write memories only when the user explicitly asks to remember "
            "something. Search memory before revising or archiving. "
            "Model-callable writes are limited to public/internal sensitivity."
        ),
    )
    try:
        asyncio.run(server.run_forever())
    except KeyboardInterrupt:
        pass
    return 0


def run_http(config: BridgeConfig, host: str, port: int) -> int:
    if not _is_loopback(host):
        print(
            "Configuration error: the panel HTTP API may only bind to a "
            "loopback host",
            file=sys.stderr,
        )
        return 2
    from .http_api import create_app

    operations = build_operations(config)
    uvicorn.run(
        create_app(operations),
        host=host,
        port=port,
        log_level="info",
        proxy_headers=False,
        server_header=False,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        load_dotenv()
        config = BridgeConfig.from_environment()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    args = parse_args(argv)
    if args.transport == "http":
        return run_http(config, args.host, args.port or config.http_port)
    return run_stdio(config)


if __name__ == "__main__":
    raise SystemExit(main())
