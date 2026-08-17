"""Vendored from ai-butler-framework memory_policy.py.

Only the pieces the bridge needs: text normalization, candidate
fingerprints, ExtractedMemory, and the local semantic encoder.
See VENDORED.md for the sync procedure."""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .models import MemoryKind, MemoryLifecycle, MemoryPolicyAction, MemorySensitivity

_SPACE = re.compile(r"\s+")
_SECRET = re.compile(
    r"(?:api[ _-]?key|access[ _-]?token|refresh[ _-]?token|session[ _-]?cookie|"
    r"password|passwd|密码|口令|私钥|密钥|-----BEGIN [A-Z ]+ PRIVATE KEY-----)",
    re.IGNORECASE,
)
_PRIVATE = re.compile(
    r"(?:身份证|银行卡|信用卡|病历|诊断|工资|收入|经纬度|家庭住址|精确位置)",
    re.IGNORECASE,
)

_SYNONYMS = {
    "简短": "简洁",
    "精简": "简洁",
    "锻炼": "运动",
    "健身": "运动",
    "早饭": "早餐",
    "汇报": "报告",
    "答复": "回答",
}


def normalize_memory_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    normalized = _SPACE.sub(" ", normalized)
    return normalized


def contains_secret(value: str) -> bool:
    return bool(_SECRET.search(value))


def contains_private_detail(value: str) -> bool:
    return bool(_PRIVATE.search(value))


def memory_fingerprint(
    content: str,
    *,
    kind: MemoryKind,
    lifecycle: MemoryLifecycle,
) -> str:
    normalized = normalize_memory_text(content).casefold()
    payload = f"{kind.value}\0{lifecycle.value}\0{normalized}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class ExtractedMemory:
    content: str
    summary: str | None
    kind: MemoryKind
    lifecycle: MemoryLifecycle
    sensitivity: MemorySensitivity
    policy_action: MemoryPolicyAction
    confidence: float
    importance: float
    policy_reason: str
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class LocalSemanticEncoder:
    """Create a local, hashed sparse vector without external data transfer."""

    model_id = "local-hash-v1"

    def __init__(self, dimensions: int = 256) -> None:
        if dimensions < 32:
            raise ValueError("dimensions must be at least 32")
        self.dimensions = dimensions

    def encode(self, content: str) -> dict[str, float]:
        normalized = normalize_memory_text(content).casefold()
        for source, target in _SYNONYMS.items():
            normalized = normalized.replace(source, target)
        compact = re.sub(r"[^\w\u3400-\u9fff]+", "", normalized)
        tokens: list[str] = []
        tokens.extend(re.findall(r"[a-z0-9_]+", normalized))
        for size in (1, 2, 3):
            tokens.extend(
                compact[index : index + size]
                for index in range(max(0, len(compact) - size + 1))
            )
        counts: dict[str, float] = {}
        for token in tokens:
            if not token:
                continue
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            key = str(index)
            counts[key] = counts.get(key, 0.0) + 1.0
        norm = math.sqrt(sum(value * value for value in counts.values()))
        if norm == 0:
            return {}
        return {key: round(value / norm, 8) for key, value in counts.items()}

    @staticmethod
    def similarity(left: dict[str, float], right: dict[str, float]) -> float:
        if not left or not right:
            return 0.0
        if len(left) > len(right):
            left, right = right, left
        return max(
            0.0,
            min(1.0, sum(value * right.get(key, 0.0) for key, value in left.items())),
        )


def recent_decay(
    created_at: datetime,
    *,
    now: datetime | None = None,
    half_life_hours: float = 48.0,
) -> float:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    created = created_at if created_at.tzinfo is not None else created_at.replace(tzinfo=UTC)
    age_hours = max(0.0, (current - created.astimezone(UTC)).total_seconds() / 3600)
    return math.pow(0.5, age_hours / half_life_hours)