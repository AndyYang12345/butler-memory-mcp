"""One-command PostgreSQL setup via Docker (explicit, user-invoked).

The bridge itself never starts containers implicitly; this command is the
explicit, observable path: probe Docker, create/start the container, wait
for health, write the env file (preserving existing keys), create the
schema, and bootstrap the principal if missing. All docker interactions
are arg-list subprocess calls (no shell), and container names/ports are
validated before use.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .vendored.config import ConfigurationError, load_dotenv
from .vendored.database import Database, DatabaseConfig
from .vendored.identity import IdentityService
from .vendored.models import Base

_CONTAINER_NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")
_IMAGE = "postgres:16-alpine"
_WAIT_SECONDS = 90


def _docker_command() -> str | None:
    return shutil.which("docker")


def _run(docker: str, *args: str, check: bool = False) -> subprocess.CompletedProcess:
    result = subprocess.run([docker, *args], capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"docker {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def _read_env(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE pairs, dropping comments and blank lines."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _write_env(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    order = [
        "AI_BUTLER_DATABASE_URL",
        "AI_BUTLER_MCP_USER_ID",
        "AI_BUTLER_MCP_DEVICE_ID",
        "AI_BUTLER_MCP_BIND",
        "AI_BUTLER_MCP_PORT",
    ]
    lines = []
    for key in order:
        if key in values:
            lines.append(f"{key}={values[key]}")
    for key in sorted(set(values) - set(order)):
        lines.append(f"{key}={values[key]}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Windows has no POSIX permissions


def _bootstrap_sync(database: Database, *, user_name: str, device_name: str,
                    device_kind: str, scopes: set[str]):
    identity = IdentityService(database)

    async def _run():
        try:
            return await identity.bootstrap(
                user_display_name=user_name,
                device_name=device_name,
                device_kind=device_kind,
                scopes=scopes,
            )
        finally:
            await database.dispose()

    return asyncio.run(_run())


def _create_schema_sync(database: Database) -> None:
    async def _run():
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
        finally:
            await database.dispose()

    asyncio.run(_run())


def run_setup_docker(args: argparse.Namespace) -> int:
    docker = _docker_command()
    if docker is None:
        print(
            "Configuration error: docker is not installed or not on PATH. "
            "Install Docker Desktop (Windows/macOS) or docker + "
            "docker-compose (Linux), then run this command again.",
            file=sys.stderr,
        )
        return 2

    try:
        _run(docker, "info", check=True)
    except RuntimeError as exc:
        print(
            f"Configuration error: docker daemon is not running ({exc}). "
            "Start Docker Desktop or `systemctl start docker`, then retry.",
            file=sys.stderr,
        )
        return 2

    name = args.container_name
    if not _CONTAINER_NAME.fullmatch(name):
        print("Configuration error: container name must match [a-zA-Z0-9_.-]+", file=sys.stderr)
        return 2
    if not 1 <= args.port <= 65535:
        print("Configuration error: port must be between 1 and 65535", file=sys.stderr)
        return 2

    # Locate or create the container.
    inspect = _run(docker, "inspect", "-f", "{{.State.Running}}", name)
    password: str | None = None
    if inspect.returncode == 0:
        if inspect.stdout.strip() == "true":
            print(f"container {name} is already running")
        else:
            print(f"starting existing container {name} ...")
            _run(docker, "start", name, check=True)
        probe = _run(docker, "exec", name, "printenv", "POSTGRES_PASSWORD")
        password = probe.stdout.strip() or None
    else:
        password = args.password or secrets.token_urlsafe(24)
        print(f"creating container {name} ({_IMAGE}) ...")
        _run(
            docker,
            "run", "-d", "--name", name,
            "-e", "POSTGRES_DB=ai_butler",
            "-e", "POSTGRES_USER=ai_butler",
            "-e", f"POSTGRES_PASSWORD={password}",
            "-p", f"127.0.0.1:{args.port}:5432",
            "-v", f"{name}-data:/var/lib/postgresql/data",
            "--restart", "unless-stopped",
            _IMAGE,
            check=True,
        )
    if not password:
        print("Configuration error: could not read the container password", file=sys.stderr)
        return 2

    # Wait for readiness.
    deadline = time.monotonic() + _WAIT_SECONDS
    ready = False
    while time.monotonic() < deadline:
        probe = _run(docker, "exec", name, "pg_isready", "-U", "ai_butler", "-d", "ai_butler")
        if probe.returncode == 0:
            ready = True
            break
        time.sleep(2)
    if not ready:
        print(f"Configuration error: postgres did not become ready within {_WAIT_SECONDS}s", file=sys.stderr)
        return 2
    print("postgres is ready")

    # Resolve and write the env file.
    env_path = (
        Path(args.env_file)
        if args.env_file
        else Path.home() / ".config" / "butler-memory-mcp" / ".env"
    )
    values = _read_env(env_path)
    values["AI_BUTLER_DATABASE_URL"] = (
        f"postgresql+asyncpg://ai_butler:{password}@127.0.0.1:{args.port}/ai_butler"
    )
    _write_env(env_path, values)
    print(f"wrote {env_path}")

    # Schema and principal, against exactly that database.
    load_dotenv(env_path)
    database = Database(DatabaseConfig.from_environment(required=True))
    _create_schema_sync(database)
    print("schema ready")

    if "AI_BUTLER_MCP_USER_ID" not in values or "AI_BUTLER_MCP_DEVICE_ID" not in values:
        scopes = set(args.scope) if args.scope else {"memory:read", "memory:write"}
        database = Database(DatabaseConfig.from_environment(required=True))
        try:
            result = _bootstrap_sync(
                database,
                user_name=args.user_name,
                device_name=args.device_name,
                device_kind=args.device_kind,
                scopes=scopes,
            )
        except ValueError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            return 2
        values["AI_BUTLER_MCP_USER_ID"] = str(result.user_id)
        values["AI_BUTLER_MCP_DEVICE_ID"] = str(result.device_id)
        _write_env(env_path, values)
        print("Device registration complete. Save this token now; it cannot be recovered later.")
        print(f"device_token={result.token.get_secret_value()}")
    else:
        print("principal already configured; bootstrap skipped")

    print("Done. The bridge is ready: ai-butler-memory-mcp (stdio) or dsh web.")
    return 0
