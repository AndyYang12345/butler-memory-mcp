"""Memory operations for the Butler Memory MCP bridge.

A thin adapter over the vendored Butler Framework memory services. No
business logic lives here: ownership, sensitivity ceilings, revision
conflicts, audit and evidence stay enforced inside
``ai_butler_memory_mcp.vendored.memory_service.MemoryService`` and
``LayeredMemoryService``. The bridge only maps MCP-shaped inputs to those
calls, normalizes outputs, and translates framework errors into codes that
are safe to show to a calling agent.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from .vendored.serializers import memory_output, memory_revision_output
from .vendored.database import Database
from .vendored.layered_memory import LayeredMemoryService
from .vendored.models import (
    MemoryCandidateStatus,
    MemoryEvidenceType,
    MemoryKind,
    MemorySensitivity,
    MemoryWriteMode,
)
from .vendored.memory_service import (
    AuthorizationError,
    InvalidMemoryError,
    MemoryService,
    ResourceNotFoundError,
    RevisionConflictError,
)

_KINDS = tuple(kind.value for kind in MemoryKind)
_CANDIDATE_STATUSES = ("pending", "auto_stored", "accepted", "rejected", "superseded")
_SENSITIVITIES = ("public", "internal")


class BridgeError(RuntimeError):
    """A domain error safe to surface to the calling agent."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def candidate_output(candidate: Any) -> dict[str, Any]:
    return {
        "candidate_id": str(candidate.id),
        "kind": candidate.kind.value,
        "lifecycle": candidate.lifecycle.value,
        "sensitivity": candidate.sensitivity.value,
        "status": candidate.status.value,
        "content": candidate.content,
        "summary": candidate.summary,
        "confidence": candidate.confidence,
        "importance": candidate.importance,
        "policy_action": candidate.policy_action.value,
        "policy_reason": candidate.policy_reason,
        "created_at": candidate.created_at.isoformat(),
        "resolved_at": (
            candidate.resolved_at.isoformat() if candidate.resolved_at else None
        ),
        "matched_memory_id": (
            str(candidate.matched_memory_id)
            if candidate.matched_memory_id is not None
            else None
        ),
    }


class MemoryOperations:
    """The complete memory surface the MCP server and HTTP API expose."""

    def __init__(self, database: Database, *, user_id: UUID, device_id: UUID) -> None:
        self._memory = MemoryService(database)
        self._layered = LayeredMemoryService(database)
        self._user_id = user_id
        self._device_id = device_id

    async def _translate(self, operation):
        try:
            return await operation
        except ResourceNotFoundError as exc:
            raise BridgeError("resource_not_found", str(exc)) from exc
        except RevisionConflictError as exc:
            raise BridgeError("revision_conflict", str(exc)) from exc
        except AuthorizationError as exc:
            raise BridgeError("memory_access_denied", str(exc)) from exc
        except (InvalidMemoryError, ValueError) as exc:
            raise BridgeError("invalid_request", str(exc)) from exc

    def _kind(self, value: str | None) -> MemoryKind | None:
        if value is None:
            return None
        try:
            return MemoryKind(value)
        except ValueError as exc:
            raise BridgeError(
                "invalid_request", f"unknown memory kind: {value!r}"
            ) from exc

    def _request_id(self) -> UUID:
        # One request id per write so the framework audit table keeps a
        # bridge-side correlation point even without a browser session.
        return uuid4()

    # -- reads -----------------------------------------------------------

    async def list_memories(
        self,
        *,
        include_archived: bool = False,
        kind: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        records = await self._translate(
            self._memory.list_memories(
                user_id=self._user_id,
                include_archived=include_archived,
                kind=self._kind(kind),
                limit=limit,
            )
        )
        return {
            "count": len(records),
            "memories": [memory_output(record) for record in records],
        }

    async def search_memories(
        self,
        *,
        query: str | None = None,
        kind: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        records = await self._translate(
            self._memory.search_memories(
                user_id=self._user_id,
                query=query,
                kind=self._kind(kind),
                limit=limit,
            )
        )
        return {
            "query": query,
            "count": len(records),
            "memories": [memory_output(record, truncate_at=2_000) for record in records],
            "sensitivity_ceiling": "internal",
        }

    async def list_revisions(self, *, memory_id: UUID) -> dict[str, Any]:
        records = await self._translate(
            self._memory.list_revisions(user_id=self._user_id, memory_id=memory_id)
        )
        return {
            "memory_id": str(memory_id),
            "count": len(records),
            "revisions": [memory_revision_output(record) for record in records],
        }

    # -- explicit writes (sensitivity ceiling: internal) ------------------

    async def create_memory(
        self,
        *,
        content: str,
        kind: str = "other",
        sensitivity: str = "internal",
        summary: str | None = None,
    ) -> dict[str, Any]:
        if sensitivity not in _SENSITIVITIES:
            raise BridgeError(
                "invalid_request",
                "model-callable memory writes are limited to public or internal",
            )
        memory = await self._translate(
            self._memory.create_memory(
                user_id=self._user_id,
                actor_device_id=self._device_id,
                content=content,
                summary=summary,
                kind=self._kind(kind) or MemoryKind.OTHER,
                sensitivity=MemorySensitivity(sensitivity),
                write_mode=MemoryWriteMode.EXPLICIT,
                evidence_type=MemoryEvidenceType.USER_STATEMENT,
                request_id=self._request_id(),
            )
        )
        return memory_output(memory)

    async def revise_memory(
        self,
        *,
        memory_id: UUID,
        expected_revision: int,
        content: str,
        reason: str,
        summary: str | None = None,
    ) -> dict[str, Any]:
        memory = await self._translate(
            self._memory.revise_memory(
                user_id=self._user_id,
                actor_device_id=self._device_id,
                memory_id=memory_id,
                expected_revision=expected_revision,
                content=content,
                summary=summary,
                reason=reason,
                request_id=self._request_id(),
            )
        )
        return memory_output(memory)

    async def archive_memory(
        self,
        *,
        memory_id: UUID,
        expected_revision: int,
        reason: str,
    ) -> dict[str, Any]:
        memory = await self._translate(
            self._memory.archive_memory(
                user_id=self._user_id,
                actor_device_id=self._device_id,
                memory_id=memory_id,
                expected_revision=expected_revision,
                reason=reason,
                request_id=self._request_id(),
            )
        )
        return memory_output(memory)

    # -- candidates (inferred facts that never silently become memory) ----

    async def list_candidates(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        if status is not None and status not in _CANDIDATE_STATUSES:
            raise BridgeError("invalid_request", f"unknown candidate status: {status!r}")
        records = await self._translate(
            self._layered.list_candidates(
                user_id=self._user_id,
                status=(
                    None
                    if status is None
                    else _candidate_status_from_string(status)
                ),
                limit=limit,
            )
        )
        return {
            "count": len(records),
            "candidates": [candidate_output(record) for record in records],
        }

    async def accept_candidate(self, *, candidate_id: UUID) -> dict[str, Any]:
        result = await self._translate(
            self._layered.accept_candidate(
                user_id=self._user_id,
                actor_device_id=self._device_id,
                candidate_id=candidate_id,
                request_id=self._request_id(),
            )
        )
        return {
            "candidate": candidate_output(result.candidate),
            "memory": memory_output(result.memory) if result.memory else None,
            "created": result.created,
        }

    async def reject_candidate(self, *, candidate_id: UUID) -> dict[str, Any]:
        record = await self._translate(
            self._layered.reject_candidate(
                user_id=self._user_id,
                actor_device_id=self._device_id,
                candidate_id=candidate_id,
                request_id=self._request_id(),
            )
        )
        return {"candidate": candidate_output(record)}


def _candidate_status_from_string(value: str):
    try:
        return MemoryCandidateStatus(value)
    except ValueError as exc:
        raise BridgeError("invalid_request", f"unknown candidate status: {value!r}") from exc


def memory_kinds() -> tuple[str, ...]:
    return _KINDS


def candidate_statuses() -> tuple[str, ...]:
    return _CANDIDATE_STATUSES
