"""Command-line entry point: ai-butler-memory-mcp.

``stdio`` serves the Model Context Protocol for DSH's dsh-mcp-client.
``http`` serves the loopback JSON API consumed by the DSH web panel's
host half. Both share one MemoryOperations instance and one principal.

Bootstrap commands (self-contained deployment, no ai-butler-framework
required):

- ``initdb`` creates the missing tables from the vendored ORM models
  (a no-op on an already-migrated database);
- ``admin bootstrap`` creates one user plus its first device and prints
  the one-time device token and the principal UUIDs.
"""

from __future__ import annotations

import argparse
import asyncio
import ipaddress
import sys

import uvicorn

from .config import BridgeConfig, load_bridge_env
from .mcp_server import StdioMcpServer
from .operations import MemoryOperations
from .tools import build_tools
from . import __version__

from .vendored.config import ConfigurationError
from .vendored.database import Database, DatabaseConfig
from .vendored.identity import DEFAULT_DEVICE_SCOPES, IdentityService
from .vendored.models import Base


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
        "--env-file",
        default=None,
        help="Explicit .env file; otherwise the standard candidates are tried.",
    )
    # Top-level serve flags keep the historical invocation
    # `ai-butler-memory-mcp --transport stdio` (used by cordis.patch.yml)
    # working; the `serve` subcommand repeats them with SUPPRESS defaults.
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default="stdio",
        help="stdio speaks MCP to DSH agents; http serves the panel API.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=None)

    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser(
        "serve",
        help="Run the bridge (default when no subcommand is given).",
    )
    serve.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default=argparse.SUPPRESS,
    )
    serve.add_argument("--host", default=argparse.SUPPRESS)
    serve.add_argument("--port", type=int, default=argparse.SUPPRESS)

    subparsers.add_parser(
        "initdb",
        help="Create missing tables from the vendored ORM models.",
    )

    admin = subparsers.add_parser(
        "admin",
        help="Local administration commands.",
    )
    admin_sub = admin.add_subparsers(dest="admin_command")
    bootstrap = admin_sub.add_parser(
        "bootstrap",
        help="Create one user plus its first device and print the token once.",
    )
    bootstrap.add_argument("--user-name", required=True)
    bootstrap.add_argument("--device-name", required=True)
    bootstrap.add_argument("--device-kind", default="agent")
    bootstrap.add_argument("--timezone", default="Asia/Shanghai")
    bootstrap.add_argument(
        "--scope",
        action="append",
        default=[],
        help="Grant one scope (repeatable); defaults to the framework set.",
    )

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
        # The panel API is plain REST: disable the websocket protocol so
        # startup never imports a websockets library (system installs may
        # carry an old version whose API uvicorn no longer accepts).
        ws="none",
    )
    return 0


def run_initdb(config: DatabaseConfig) -> int:
    database = Database(config)

    async def _run() -> None:
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        finally:
            await database.dispose()

    asyncio.run(_run())
    print("schema ready: all missing butler-memory tables created")
    return 0


def run_admin_bootstrap(config: DatabaseConfig, args: argparse.Namespace) -> int:
    database = Database(config)
    identity = IdentityService(database)
    scopes = set(args.scope) if args.scope else set(DEFAULT_DEVICE_SCOPES)

    async def _run():
        try:
            return await identity.bootstrap(
                user_display_name=args.user_name,
                device_name=args.device_name,
                device_kind=args.device_kind,
                timezone=args.timezone,
                scopes=scopes,
            )
        finally:
            await database.dispose()

    try:
        result = asyncio.run(_run())
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    print("Device registration complete. Save this token now; it cannot be recovered later.")
    print(f"user_id={result.user_id}")
    print(f"device_id={result.device_id}")
    print(f"credential_id={result.credential_id}")
    print(f"device_token={result.token.get_secret_value()}")
    print("Put user_id/device_id into AI_BUTLER_MCP_USER_ID/AI_BUTLER_MCP_DEVICE_ID.")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        load_bridge_env(args.env_file)
        database_config = DatabaseConfig.from_environment(required=True)
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if args.command == "initdb":
        return run_initdb(database_config)
    if args.command == "admin":
        if args.admin_command == "bootstrap":
            return run_admin_bootstrap(database_config, args)
        print("Configuration error: unknown admin command", file=sys.stderr)
        return 2

    # serve (default)
    try:
        config = BridgeConfig.from_environment()
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    if args.transport == "http":
        return run_http(config, args.host, args.port or config.http_port)
    return run_stdio(config)


if __name__ == "__main__":
    raise SystemExit(main())
