"""Timezone detection for local clients."""

from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def validate_timezone(value: str) -> str:
    """Return a valid IANA timezone name or raise ValueError."""

    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Invalid IANA timezone: {value}") from exc
    return value


def detect_local_timezone(default: str = "UTC") -> str:
    """Detect an IANA timezone without trusting local wall-clock text."""

    candidates: list[str] = []
    environment_timezone = os.environ.get("TZ")
    if environment_timezone:
        candidates.append(environment_timezone.lstrip(":"))

    timezone_file = Path("/etc/timezone")
    try:
        configured_timezone = timezone_file.read_text(encoding="utf-8").strip()
    except OSError:
        configured_timezone = ""
    if configured_timezone:
        candidates.append(configured_timezone)

    localtime = Path("/etc/localtime")
    try:
        resolved = localtime.resolve(strict=True)
    except OSError:
        resolved = None
    if resolved is not None:
        marker = "/zoneinfo/"
        resolved_text = str(resolved)
        if marker in resolved_text:
            candidates.append(resolved_text.split(marker, maxsplit=1)[1])

    candidates.append(default)
    for candidate in candidates:
        try:
            return validate_timezone(candidate)
        except ValueError:
            continue
    return "UTC"
