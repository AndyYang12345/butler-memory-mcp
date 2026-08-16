"""Secret-safe configuration for the Butler Memory MCP bridge.

Reuses the framework's own ``DatabaseConfig`` so the production PostgreSQL
target, driver allowlist and error wording stay identical to the parent
project. The bridge acts as ONE durable principal: a dedicated device that
the deployer registers through ``ai-butler-admin add-device``. Ownership,
scope and audit checks therefore remain enforced inside the framework.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from ai_butler_runtime.config import ConfigurationError
from ai_butler_runtime.persistence.database import DatabaseConfig


@dataclass(frozen=True, slots=True)
class BridgeConfig:
    database: DatabaseConfig
    user_id: UUID
    device_id: UUID
    http_bind: str = "127.0.0.1"
    http_port: int = 8771

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "BridgeConfig":
        source = os.environ if environment is None else environment

        database = DatabaseConfig.from_environment(
            environment=source, required=True
        )
        if database is None:  # pragma: no cover - required=True above
            raise ConfigurationError("AI_BUTLER_DATABASE_URL is not configured")

        raw_user = source.get("AI_BUTLER_MCP_USER_ID", "").strip()
        raw_device = source.get("AI_BUTLER_MCP_DEVICE_ID", "").strip()
        try:
            user_id = UUID(raw_user)
            device_id = UUID(raw_device)
        except ValueError as exc:
            raise ConfigurationError(
                "AI_BUTLER_MCP_USER_ID and AI_BUTLER_MCP_DEVICE_ID must be valid "
                "UUIDs. Create the bridge device once with:\n"
                "  ai-butler-admin add-device --user-id <USER_UUID> "
                "--device-name dsh-agent --device-kind agent "
                "--scope memory:read --scope memory:write\n"
                "and copy the returned credential UUID into these variables."
            ) from exc

        return cls(
            database=database,
            user_id=user_id,
            device_id=device_id,
            http_bind=source.get("AI_BUTLER_MCP_BIND", "127.0.0.1").strip(),
            http_port=cls._parse_port(source.get("AI_BUTLER_MCP_PORT", "8771")),
        )

    @staticmethod
    def _parse_port(value: str) -> int:
        try:
            port = int(value)
        except ValueError as exc:
            raise ConfigurationError("AI_BUTLER_MCP_PORT must be an integer") from exc
        if not 1 <= port <= 65_535:
            raise ConfigurationError(
                "AI_BUTLER_MCP_PORT must be between 1 and 65535"
            )
        return port
