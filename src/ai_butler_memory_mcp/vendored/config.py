"""Small, secret-safe local configuration loader."""

from __future__ import annotations

import os
import re
from binascii import Error as Base64Error
from base64 import urlsafe_b64decode
from pathlib import Path
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class ConfigurationError(RuntimeError):
    """A configuration problem safe to show to a local operator."""


class ToolIntentEncryptionConfig(BaseModel):
    """Secret material used only for short-lived resumable Tool payloads."""

    model_config = ConfigDict(extra="forbid")

    key: SecretStr

    @property
    def key_bytes(self) -> bytes:
        encoded = self.key.get_secret_value().strip()
        try:
            decoded = urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        except (Base64Error, ValueError) as exc:
            raise ConfigurationError(
                "AI_BUTLER_INTENT_ENCRYPTION_KEY is invalid"
            ) from exc
        if len(decoded) != 32:
            raise ConfigurationError(
                "AI_BUTLER_INTENT_ENCRYPTION_KEY must encode exactly 32 bytes"
            )
        return decoded

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
        *,
        required: bool = True,
    ) -> "ToolIntentEncryptionConfig | None":
        source = os.environ if environment is None else environment
        raw_key = source.get("AI_BUTLER_INTENT_ENCRYPTION_KEY", "").strip()
        if not raw_key:
            if required:
                raise ConfigurationError(
                    "AI_BUTLER_INTENT_ENCRYPTION_KEY is not configured"
                )
            return None
        config = cls(key=raw_key)
        config.key_bytes
        return config


def load_dotenv(path: str | Path = ".env") -> None:
    """Load a minimal dotenv file without overriding process environment.

    Values are never logged or returned. The parser deliberately supports only
    the simple KEY=VALUE form needed by this project.
    """

    dotenv_path = Path(path)
    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ConfigurationError(f"Cannot read {dotenv_path}") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ConfigurationError(
                f"Invalid configuration line {line_number} in {dotenv_path}"
            )
        name, value = line.split("=", maxsplit=1)
        name = name.strip()
        if not _ENV_NAME.fullmatch(name):
            raise ConfigurationError(
                f"Invalid variable name on line {line_number} in {dotenv_path}"
            )
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(name, value)

