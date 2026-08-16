"""Vendored from ai-butler-framework persistence/services.py: MemoryService slice plus private helpers."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .memory_policy import LocalSemanticEncoder, normalize_memory_text, recent_decay
from .models import (
    AuditLog,
    ChatMessage,
    ChatSession,
    Device,
    DeviceStatus,
    Memory,
    MemoryEvidence,
    MemoryEvidenceType,
    MemoryKind,
    MemoryLifecycle,
    MemoryRevision,
    MemorySensitivity,
    MemoryStatus,
    MemoryWriteMode,
    utc_now,
)


class PersistenceServiceError(RuntimeError):
    pass


class AuthorizationError(PersistenceServiceError):
    pass


class ResourceNotFoundError(PersistenceServiceError):
    pass


class RevisionConflictError(PersistenceServiceError):
    pass


class InvalidMemoryError(PersistenceServiceError):
    pass

def _clean_text(value: str, field: str, *, maximum: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} must not be blank")
    if len(normalized) > maximum:
        raise ValueError(f"{field} exceeds {maximum} characters")
    return normalized


def _validated_scopes(scopes: set[str] | frozenset[str]) -> frozenset[str]:
    normalized = frozenset(scope.strip() for scope in scopes)
    if not normalized or any(not _SCOPE.fullmatch(scope) for scope in normalized):
        raise ValueError("Scopes must use resource:action names")
    return normalized


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _digest_bytes(value: str, field: str) -> bytes:
    try:
        digest = bytes.fromhex(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be a SHA-256 hex digest") from exc
    if len(digest) != 32:
        raise ValueError(f"{field} must be a SHA-256 hex digest")
    return digest


def _audit(
    session: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: UUID | None,
    outcome: str = "success",
    actor_user_id: UUID | None = None,
    actor_device_id: UUID | None = None,
    request_id: UUID | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_user_id=actor_user_id,
            actor_device_id=actor_device_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            outcome=outcome,
            request_id=request_id,
            event_data=metadata or {},
        )
    )


async def _ensure_device_owner(
    session: AsyncSession, user_id: UUID, device_id: UUID
) -> None:
    owner = await session.scalar(
        select(Device.user_id).where(
            Device.id == device_id,
            Device.status == DeviceStatus.ACTIVE,
        )
    )
    if owner != user_id:
        raise AuthorizationError("Device is not authorized for this user")



class MemoryService:
    def __init__(self, database: Database) -> None:
        self.database = database
        self._semantic_encoder = LocalSemanticEncoder()

    async def create_memory(
        self,
        *,
        user_id: UUID,
        actor_device_id: UUID,
        content: str,
        kind: MemoryKind,
        sensitivity: MemorySensitivity,
        write_mode: MemoryWriteMode,
        summary: str | None = None,
        source_session_id: UUID | None = None,
        source_message_id: UUID | None = None,
        evidence_type: MemoryEvidenceType = MemoryEvidenceType.USER_STATEMENT,
        source_reference: str | None = None,
        request_id: UUID | None = None,
    ) -> Memory:
        content = _clean_text(content, "content", maximum=100_000)
        normalized_summary = summary.strip() if summary else None
        if normalized_summary and len(normalized_summary) > 10_000:
            raise InvalidMemoryError("summary exceeds 10000 characters")
        if write_mode == MemoryWriteMode.AUTOMATIC and sensitivity in {
            MemorySensitivity.PRIVATE,
            MemorySensitivity.SECRET,
        }:
            raise InvalidMemoryError(
                "Automatic memory writes are limited to low-sensitivity data"
            )

        embedding_features = self._semantic_encoder.encode(
            f"{normalized_summary or ''} {content}".strip()
        )
        memory = Memory(
            user_id=user_id,
            kind=kind,
            sensitivity=sensitivity,
            write_mode=write_mode,
            lifecycle=MemoryLifecycle.DURABLE,
            content=content,
            summary=normalized_summary,
            confidence=1.0,
            importance=0.7 if kind == MemoryKind.PREFERENCE else 0.6,
            embedding_model=(
                self._semantic_encoder.model_id if embedding_features else None
            ),
            embedding_features=embedding_features or None,
            source_session_id=source_session_id,
            source_message_id=source_message_id,
        )
        async with self.database.session() as session:
            await _ensure_device_owner(session, user_id, actor_device_id)
            await self._validate_sources(
                session,
                user_id=user_id,
                session_id=source_session_id,
                message_id=source_message_id,
            )
            session.add(memory)
            await session.flush()
            session.add(
                MemoryRevision(
                    memory_id=memory.id,
                    revision=1,
                    content=content,
                    summary=normalized_summary,
                    reason="created",
                    actor_device_id=actor_device_id,
                )
            )
            session.add(
                MemoryEvidence(
                    memory_id=memory.id,
                    evidence_type=evidence_type,
                    source_message_id=source_message_id,
                    source_reference=source_reference,
                )
            )
            _audit(
                session,
                action="memory.create",
                resource_type="memory",
                resource_id=memory.id,
                actor_user_id=user_id,
                actor_device_id=actor_device_id,
                request_id=request_id,
                metadata={
                    "kind": kind.value,
                    "sensitivity": sensitivity.value,
                    "write_mode": write_mode.value,
                    "revision": 1,
                },
            )
        return memory

    async def revise_memory(
        self,
        *,
        user_id: UUID,
        actor_device_id: UUID,
        memory_id: UUID,
        expected_revision: int,
        content: str,
        reason: str,
        summary: str | None = None,
        request_id: UUID | None = None,
    ) -> Memory:
        content = _clean_text(content, "content", maximum=100_000)
        reason = _clean_text(reason, "reason", maximum=500)
        normalized_summary = summary.strip() if summary else None
        if normalized_summary and len(normalized_summary) > 10_000:
            raise InvalidMemoryError("summary exceeds 10000 characters")

        async with self.database.session() as session:
            await _ensure_device_owner(session, user_id, actor_device_id)
            memory = await session.scalar(
                select(Memory)
                .where(
                    Memory.id == memory_id,
                    Memory.user_id == user_id,
                    Memory.status != MemoryStatus.DELETED,
                )
                .with_for_update()
            )
            if memory is None:
                raise ResourceNotFoundError("Memory does not exist")
            if memory.current_revision != expected_revision:
                raise RevisionConflictError("Memory revision is stale")
            next_revision = expected_revision + 1
            memory.content = content
            memory.summary = normalized_summary
            embedding_features = self._semantic_encoder.encode(
                f"{normalized_summary or ''} {content}".strip()
            )
            memory.embedding_model = (
                self._semantic_encoder.model_id if embedding_features else None
            )
            memory.embedding_features = embedding_features or None
            memory.current_revision = next_revision
            session.add(
                MemoryRevision(
                    memory_id=memory.id,
                    revision=next_revision,
                    content=content,
                    summary=normalized_summary,
                    reason=reason,
                    actor_device_id=actor_device_id,
                )
            )
            _audit(
                session,
                action="memory.revise",
                resource_type="memory",
                resource_id=memory.id,
                actor_user_id=user_id,
                actor_device_id=actor_device_id,
                request_id=request_id,
                metadata={"revision": next_revision},
            )
            await session.flush()
            return memory

    async def archive_memory(
        self,
        *,
        user_id: UUID,
        actor_device_id: UUID,
        memory_id: UUID,
        expected_revision: int,
        reason: str,
        request_id: UUID | None = None,
    ) -> Memory:
        reason = _clean_text(reason, "reason", maximum=500)
        async with self.database.session() as session:
            await _ensure_device_owner(session, user_id, actor_device_id)
            memory = await session.scalar(
                select(Memory)
                .where(Memory.id == memory_id, Memory.user_id == user_id)
                .with_for_update()
            )
            if memory is None:
                raise ResourceNotFoundError("Memory does not exist")
            if memory.current_revision != expected_revision:
                raise RevisionConflictError("Memory revision is stale")
            if memory.status == MemoryStatus.DELETED:
                raise ResourceNotFoundError("Memory does not exist")
            next_revision = expected_revision + 1
            memory.status = MemoryStatus.ARCHIVED
            memory.current_revision = next_revision
            session.add(
                MemoryRevision(
                    memory_id=memory.id,
                    revision=next_revision,
                    content=memory.content,
                    summary=memory.summary,
                    reason=reason,
                    actor_device_id=actor_device_id,
                )
            )
            _audit(
                session,
                action="memory.archive",
                resource_type="memory",
                resource_id=memory.id,
                actor_user_id=user_id,
                actor_device_id=actor_device_id,
                request_id=request_id,
                metadata={"revision": next_revision},
            )
            await session.flush()
            return memory

    async def list_memories(
        self,
        *,
        user_id: UUID,
        include_archived: bool = False,
        kind: MemoryKind | None = None,
        limit: int = 50,
    ) -> list[Memory]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        statuses = [MemoryStatus.ACTIVE]
        if include_archived:
            statuses.append(MemoryStatus.ARCHIVED)
        statement = select(Memory).where(
            Memory.user_id == user_id,
            Memory.status.in_(statuses),
        )
        if kind is not None:
            statement = statement.where(Memory.kind == kind)
        async with self.database.session() as session:
            return list(
                (
                    await session.scalars(
                        statement.order_by(Memory.updated_at.desc()).limit(limit)
                    )
                ).all()
            )

    async def search_memories(
        self,
        *,
        user_id: UUID,
        query: str | None = None,
        kind: MemoryKind | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")
        normalized_query = normalize_memory_text(query) if query else None
        if normalized_query is not None and len(normalized_query) > 500:
            raise ValueError("query exceeds 500 characters")
        current = utc_now()
        statement = select(Memory).where(
            Memory.user_id == user_id,
            Memory.status == MemoryStatus.ACTIVE,
            Memory.sensitivity.in_(
                [MemorySensitivity.PUBLIC, MemorySensitivity.INTERNAL]
            ),
            or_(Memory.valid_from.is_(None), Memory.valid_from <= current),
            or_(Memory.valid_until.is_(None), Memory.valid_until > current),
        )
        if kind is not None:
            statement = statement.where(Memory.kind == kind)
        async with self.database.session() as session:
            records = list(
                (
                    await session.scalars(
                        statement.order_by(Memory.updated_at.desc()).limit(250)
                    )
                ).all()
            )
        if not normalized_query:
            return records[:limit]
        query_features = self._semantic_encoder.encode(normalized_query)
        query_folded = normalized_query.casefold()
        query_terms = set(re.findall(r"[\w\u3400-\u9fff]{2,}", query_folded))
        scored: list[tuple[Memory, float]] = []
        for memory in records:
            searchable = f"{memory.summary or ''} {memory.content}".strip()
            folded = searchable.casefold()
            lexical = 1.0 if query_folded in folded else 0.0
            searchable_terms = set(re.findall(r"[\w\u3400-\u9fff]{2,}", folded))
            if query_terms:
                lexical = max(
                    lexical,
                    len(query_terms & searchable_terms) / len(query_terms),
                )
            semantic = self._semantic_encoder.similarity(
                query_features,
                memory.embedding_features
                or self._semantic_encoder.encode(searchable),
            )
            recency = (
                recent_decay(memory.created_at, now=current)
                if memory.lifecycle == MemoryLifecycle.RECENT
                else 0.5
            )
            score = (
                0.35 * lexical
                + 0.45 * semantic
                + 0.10 * recency
                + 0.10 * memory.importance
            )
            if score >= 0.12:
                scored.append((memory, score))
        scored.sort(key=lambda item: (item[1], item[0].updated_at), reverse=True)
        return [memory for memory, _score in scored[:limit]]

    async def list_revisions(
        self, *, user_id: UUID, memory_id: UUID
    ) -> list[MemoryRevision]:
        async with self.database.session() as session:
            owns_memory = await session.scalar(
                select(Memory.id).where(
                    Memory.id == memory_id,
                    Memory.user_id == user_id,
                )
            )
            if owns_memory is None:
                raise ResourceNotFoundError("Memory does not exist")
            return list(
                (
                    await session.scalars(
                        select(MemoryRevision)
                        .where(MemoryRevision.memory_id == memory_id)
                        .order_by(MemoryRevision.revision)
                    )
                ).all()
            )

    @staticmethod
    async def _validate_sources(
        session: AsyncSession,
        *,
        user_id: UUID,
        session_id: UUID | None,
        message_id: UUID | None,
    ) -> None:
        if session_id is not None:
            owner = await session.scalar(
                select(ChatSession.user_id).where(ChatSession.id == session_id)
            )
            if owner != user_id:
                raise AuthorizationError("Memory source session is not owned by user")
        if message_id is not None:
            owner = await session.scalar(
                select(ChatSession.user_id)
                .join(ChatMessage, ChatMessage.session_id == ChatSession.id)
                .where(ChatMessage.id == message_id)
            )
            if owner != user_id:
                raise AuthorizationError("Memory source message is not owned by user")