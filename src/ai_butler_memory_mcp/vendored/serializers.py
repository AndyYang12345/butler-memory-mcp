"""Vendored memory output serializers from ai-butler-framework."""

from __future__ import annotations

from typing import Any


def memory_output(memory: Any, *, truncate_at: int | None = None) -> dict[str, Any]:
    content = memory.content
    truncated = truncate_at is not None and len(content) > truncate_at
    if truncate_at is not None:
        content = content[:truncate_at]
    return {
        "memory_id": str(memory.id),
        "kind": memory.kind.value,
        "sensitivity": memory.sensitivity.value,
        "status": memory.status.value,
        "lifecycle": memory.lifecycle.value,
        "summary": memory.summary,
        "content": content,
        "truncated": truncated,
        "revision": memory.current_revision,
        "confidence": memory.confidence,
        "importance": memory.importance,
        "valid_from": (
            memory.valid_from.isoformat() if memory.valid_from is not None else None
        ),
        "valid_until": (
            memory.valid_until.isoformat() if memory.valid_until is not None else None
        ),
        "created_at": memory.created_at.isoformat(),
        "updated_at": memory.updated_at.isoformat(),
    }


def memory_revision_output(revision: Any) -> dict[str, Any]:
    return {
        "revision": revision.revision,
        "content": revision.content,
        "summary": revision.summary,
        "reason": revision.reason,
        "actor_device_id": (
            str(revision.actor_device_id)
            if revision.actor_device_id is not None
            else None
        ),
        "created_at": revision.created_at.isoformat(),
    }
