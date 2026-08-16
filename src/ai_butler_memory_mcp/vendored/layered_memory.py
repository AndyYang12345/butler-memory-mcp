"""Vendored from ai-butler-framework persistence/memory_services.py: candidate helpers plus LayeredMemoryService."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select

from .database import Database
from .memory_policy import (
    ExtractedMemory,
    LocalSemanticEncoder,
    memory_fingerprint,
    normalize_memory_text,
    recent_decay,
)
from .memory_service import (
    AuthorizationError,
    InvalidMemoryError,
    ResourceNotFoundError,
    RevisionConflictError,
)
from .models import (
    AuditLog,
    ChatMessage,
    ChatSession,
    Device,
    Memory,
    MemoryCandidate,
    MemoryCandidateStatus,
    MemoryEvidence,
    MemoryEvidenceType,
    MemoryKind,
    MemoryLifecycle,
    MemoryPolicyAction,
    MemoryRevision,
    MemorySensitivity,
    MemoryStatus,
    MemoryWriteMode,
    utc_now,
)


def _audit(
    session,
    *,
    action: str,
    resource_type: str,
    resource_id: UUID | None,
    actor_user_id: UUID | None,
    actor_device_id: UUID | None,
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
            outcome="success",
            request_id=request_id,
            event_data=metadata or {},
        )
    )


async def _ensure_owner(session, user_id: UUID, device_id: UUID) -> None:
    owned = await session.scalar(
        select(Device.id).where(Device.id == device_id, Device.user_id == user_id)
    )
    if owned is None:
        raise AuthorizationError("Device is not owned by the user")


async def _validate_sources(
    session,
    *,
    user_id: UUID,
    source_session_id: UUID | None,
    source_message_id: UUID | None,
) -> None:
    if source_session_id is not None:
        owned_session = await session.scalar(
            select(ChatSession.id).where(
                ChatSession.id == source_session_id,
                ChatSession.user_id == user_id,
            )
        )
        if owned_session is None:
            raise AuthorizationError("Source session is not owned by the user")
    if source_message_id is not None:
        owned_message = await session.scalar(
            select(ChatMessage.id)
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(
                ChatMessage.id == source_message_id,
                ChatSession.user_id == user_id,
            )
        )
        if owned_message is None:
            raise AuthorizationError("Source message is not owned by the user")


def _memory_revision(
    memory: Memory,
    *,
    actor_device_id: UUID | None,
    reason: str,
) -> MemoryRevision:
    return MemoryRevision(
        memory_id=memory.id,
        revision=memory.current_revision,
        content=memory.content,
        summary=memory.summary,
        reason=reason,
        actor_device_id=actor_device_id,
    )


def _new_memory(
    proposal: ExtractedMemory,
    *,
    user_id: UUID,
    source_session_id: UUID | None,
    source_message_id: UUID | None,
    encoder: LocalSemanticEncoder,
) -> Memory:
    features = encoder.encode(proposal.content)
    return Memory(
        user_id=user_id,
        kind=proposal.kind,
        sensitivity=proposal.sensitivity,
        write_mode=MemoryWriteMode.AUTOMATIC,
        lifecycle=proposal.lifecycle,
        content=proposal.content,
        summary=proposal.summary,
        confidence=proposal.confidence,
        importance=proposal.importance,
        embedding_model=encoder.model_id if features else None,
        embedding_features=features or None,
        source_session_id=source_session_id,
        source_message_id=source_message_id,
        valid_from=proposal.valid_from,
        valid_until=proposal.valid_until,
    )


@dataclass(frozen=True, slots=True)
class CandidateRecordResult:
    candidate: MemoryCandidate
    memory: Memory | None
    created: bool


class LayeredMemoryService:
    def __init__(
        self,
        database: Database,
        *,
        encoder: LocalSemanticEncoder | None = None,
    ) -> None:
        self.database = database
        self.encoder = encoder or LocalSemanticEncoder()

    async def record_candidate(
        self,
        *,
        user_id: UUID,
        actor_device_id: UUID,
        proposal: ExtractedMemory,
        source_session_id: UUID | None = None,
        source_message_id: UUID | None = None,
        request_id: UUID | None = None,
    ) -> CandidateRecordResult:
        content = normalize_memory_text(proposal.content)
        if not content:
            raise InvalidMemoryError("candidate content must not be blank")
        if proposal.sensitivity == MemorySensitivity.SECRET:
            raise InvalidMemoryError("Secret content cannot enter memory candidates")
        if proposal.policy_action == MemoryPolicyAction.AUTO_STORE and (
            proposal.sensitivity not in {MemorySensitivity.PUBLIC, MemorySensitivity.INTERNAL}
        ):
            raise InvalidMemoryError("Automatic capture is limited to low-sensitivity data")
        fingerprint = memory_fingerprint(
            content,
            kind=proposal.kind,
            lifecycle=proposal.lifecycle,
        )
        async with self.database.session() as session:
            await _ensure_owner(session, user_id, actor_device_id)
            await _validate_sources(
                session,
                user_id=user_id,
                source_session_id=source_session_id,
                source_message_id=source_message_id,
            )
            existing_candidate = await session.scalar(
                select(MemoryCandidate).where(
                    MemoryCandidate.user_id == user_id,
                    MemoryCandidate.fingerprint == fingerprint,
                )
            )
            if existing_candidate is not None:
                memory = (
                    await session.get(Memory, existing_candidate.matched_memory_id)
                    if existing_candidate.matched_memory_id is not None
                    else None
                )
                return CandidateRecordResult(existing_candidate, memory, False)

            exact_memory = await session.scalar(
                select(Memory).where(
                    Memory.user_id == user_id,
                    Memory.status == MemoryStatus.ACTIVE,
                    Memory.kind == proposal.kind,
                    Memory.lifecycle == proposal.lifecycle,
                    func.lower(Memory.content) == content.casefold(),
                )
            )
            policy_action = proposal.policy_action
            status = MemoryCandidateStatus.PENDING
            matched_memory = exact_memory
            policy_reason = proposal.policy_reason
            if exact_memory is not None:
                status = MemoryCandidateStatus.SUPERSEDED
                policy_reason = "exact_active_memory_already_exists"
            elif proposal.lifecycle == MemoryLifecycle.DURABLE:
                possible_conflicts = list(
                    (
                        await session.scalars(
                            select(Memory)
                            .where(
                                Memory.user_id == user_id,
                                Memory.status == MemoryStatus.ACTIVE,
                                Memory.kind == proposal.kind,
                                Memory.lifecycle == MemoryLifecycle.DURABLE,
                                Memory.sensitivity.in_(
                                    [
                                        MemorySensitivity.PUBLIC,
                                        MemorySensitivity.INTERNAL,
                                    ]
                                ),
                            )
                            .order_by(Memory.updated_at.desc())
                            .limit(50)
                        )
                    ).all()
                )
                proposal_features = self.encoder.encode(content)
                best_similarity = 0.0
                for candidate_memory in possible_conflicts:
                    features = candidate_memory.embedding_features or self.encoder.encode(
                        candidate_memory.content
                    )
                    similarity = self.encoder.similarity(proposal_features, features)
                    if similarity > best_similarity:
                        best_similarity = similarity
                        matched_memory = candidate_memory
                if matched_memory is not None and best_similarity >= 0.72:
                    policy_action = MemoryPolicyAction.CONFIRM
                    policy_reason = "similar_durable_memory_requires_conflict_resolution"

            candidate = MemoryCandidate(
                user_id=user_id,
                actor_device_id=actor_device_id,
                source_session_id=source_session_id,
                source_message_id=source_message_id,
                kind=proposal.kind,
                lifecycle=proposal.lifecycle,
                sensitivity=proposal.sensitivity,
                policy_action=policy_action,
                status=status,
                content=content,
                summary=proposal.summary,
                fingerprint=fingerprint,
                confidence=proposal.confidence,
                importance=proposal.importance,
                policy_reason=policy_reason,
                valid_from=proposal.valid_from,
                valid_until=proposal.valid_until,
                matched_memory_id=(matched_memory.id if matched_memory is not None else None),
                resolved_at=utc_now() if status == MemoryCandidateStatus.SUPERSEDED else None,
            )
            session.add(candidate)
            await session.flush()
            memory: Memory | None = None
            if (
                status == MemoryCandidateStatus.PENDING
                and policy_action == MemoryPolicyAction.AUTO_STORE
            ):
                memory = _new_memory(
                    proposal,
                    user_id=user_id,
                    source_session_id=source_session_id,
                    source_message_id=source_message_id,
                    encoder=self.encoder,
                )
                session.add(memory)
                await session.flush()
                session.add(
                    _memory_revision(
                        memory,
                        actor_device_id=actor_device_id,
                        reason="automatic_recent_capture",
                    )
                )
                session.add(
                    MemoryEvidence(
                        memory_id=memory.id,
                        evidence_type=MemoryEvidenceType.CONVERSATION,
                        source_message_id=source_message_id,
                        source_reference="automatic_turn_extraction",
                    )
                )
                candidate.status = MemoryCandidateStatus.AUTO_STORED
                candidate.matched_memory_id = memory.id
                candidate.resolved_at = utc_now()
                _audit(
                    session,
                    action="memory.create.automatic",
                    resource_type="memory",
                    resource_id=memory.id,
                    actor_user_id=user_id,
                    actor_device_id=actor_device_id,
                    request_id=request_id,
                    metadata={
                        "kind": memory.kind.value,
                        "lifecycle": memory.lifecycle.value,
                        "sensitivity": memory.sensitivity.value,
                        "candidate_id": str(candidate.id),
                    },
                )
            _audit(
                session,
                action="memory_candidate.create",
                resource_type="memory_candidate",
                resource_id=candidate.id,
                actor_user_id=user_id,
                actor_device_id=actor_device_id,
                request_id=request_id,
                metadata={
                    "kind": candidate.kind.value,
                    "lifecycle": candidate.lifecycle.value,
                    "sensitivity": candidate.sensitivity.value,
                    "policy_action": candidate.policy_action.value,
                    "status": candidate.status.value,
                    "has_source_message": source_message_id is not None,
                },
            )
            await session.flush()
            return CandidateRecordResult(candidate, memory, True)

    async def list_candidates(
        self,
        *,
        user_id: UUID,
        status: MemoryCandidateStatus | None = None,
        limit: int = 50,
    ) -> list[MemoryCandidate]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        statement = select(MemoryCandidate).where(MemoryCandidate.user_id == user_id)
        if status is not None:
            statement = statement.where(MemoryCandidate.status == status)
        async with self.database.session() as session:
            return list(
                (
                    await session.scalars(
                        statement.order_by(MemoryCandidate.created_at.desc()).limit(limit)
                    )
                ).all()
            )

    async def accept_candidate(
        self,
        *,
        user_id: UUID,
        actor_device_id: UUID,
        candidate_id: UUID,
        request_id: UUID | None = None,
    ) -> CandidateRecordResult:
        async with self.database.session() as session:
            await _ensure_owner(session, user_id, actor_device_id)
            candidate = await session.scalar(
                select(MemoryCandidate).where(
                    MemoryCandidate.id == candidate_id,
                    MemoryCandidate.user_id == user_id,
                )
            )
            if candidate is None:
                raise ResourceNotFoundError("Memory candidate does not exist")
            if candidate.status != MemoryCandidateStatus.PENDING:
                raise RevisionConflictError("Memory candidate is already resolved")
            proposal = ExtractedMemory(
                content=candidate.content,
                summary=candidate.summary,
                kind=candidate.kind,
                lifecycle=candidate.lifecycle,
                sensitivity=candidate.sensitivity,
                policy_action=MemoryPolicyAction.CONFIRM,
                confidence=candidate.confidence,
                importance=candidate.importance,
                policy_reason=candidate.policy_reason,
                valid_from=candidate.valid_from,
                valid_until=candidate.valid_until,
            )
            memory = _new_memory(
                proposal,
                user_id=user_id,
                source_session_id=candidate.source_session_id,
                source_message_id=candidate.source_message_id,
                encoder=self.encoder,
            )
            session.add(memory)
            await session.flush()
            session.add(
                _memory_revision(
                    memory,
                    actor_device_id=actor_device_id,
                    reason="accepted_memory_candidate",
                )
            )
            session.add(
                MemoryEvidence(
                    memory_id=memory.id,
                    evidence_type=MemoryEvidenceType.CONVERSATION,
                    source_message_id=candidate.source_message_id,
                    source_reference="accepted_memory_candidate",
                )
            )
            candidate.status = MemoryCandidateStatus.ACCEPTED
            candidate.matched_memory_id = memory.id
            candidate.resolved_at = utc_now()
            _audit(
                session,
                action="memory_candidate.accept",
                resource_type="memory_candidate",
                resource_id=candidate.id,
                actor_user_id=user_id,
                actor_device_id=actor_device_id,
                request_id=request_id,
                metadata={"memory_id": str(memory.id)},
            )
            return CandidateRecordResult(candidate, memory, False)

    async def reject_candidate(
        self,
        *,
        user_id: UUID,
        actor_device_id: UUID,
        candidate_id: UUID,
        request_id: UUID | None = None,
    ) -> MemoryCandidate:
        async with self.database.session() as session:
            await _ensure_owner(session, user_id, actor_device_id)
            candidate = await session.scalar(
                select(MemoryCandidate).where(
                    MemoryCandidate.id == candidate_id,
                    MemoryCandidate.user_id == user_id,
                )
            )
            if candidate is None:
                raise ResourceNotFoundError("Memory candidate does not exist")
            if candidate.status != MemoryCandidateStatus.PENDING:
                raise RevisionConflictError("Memory candidate is already resolved")
            candidate.status = MemoryCandidateStatus.REJECTED
            candidate.resolved_at = utc_now()
            _audit(
                session,
                action="memory_candidate.reject",
                resource_type="memory_candidate",
                resource_id=candidate.id,
                actor_user_id=user_id,
                actor_device_id=actor_device_id,
                request_id=request_id,
                metadata={"kind": candidate.kind.value},
            )
            return candidate

    async def archive_expired_recent(
        self,
        *,
        now: datetime | None = None,
    ) -> int:
        current = (now or utc_now()).astimezone(UTC)
        async with self.database.session() as session:
            records = list(
                (
                    await session.scalars(
                        select(Memory).where(
                            Memory.status == MemoryStatus.ACTIVE,
                            Memory.lifecycle == MemoryLifecycle.RECENT,
                            Memory.valid_until.is_not(None),
                            Memory.valid_until <= current,
                        )
                    )
                ).all()
            )
            for memory in records:
                memory.status = MemoryStatus.ARCHIVED
                memory.current_revision += 1
                session.add(
                    _memory_revision(
                        memory,
                        actor_device_id=None,
                        reason="recent_memory_expired",
                    )
                )
                _audit(
                    session,
                    action="memory.archive.expired",
                    resource_type="memory",
                    resource_id=memory.id,
                    actor_user_id=memory.user_id,
                    actor_device_id=None,
                    metadata={"revision": memory.current_revision},
                )
            return len(records)

    async def propose_recent_consolidation(
        self,
        *,
        user_id: UUID,
        actor_device_id: UUID,
        request_id: UUID | None = None,
    ) -> CandidateRecordResult | None:
        """Turn repeated episodes into a durable candidate, never a durable fact."""

        current = utc_now()
        async with self.database.session() as session:
            await _ensure_owner(session, user_id, actor_device_id)
            episodes = list(
                (
                    await session.scalars(
                        select(Memory)
                        .where(
                            Memory.user_id == user_id,
                            Memory.status == MemoryStatus.ACTIVE,
                            Memory.lifecycle == MemoryLifecycle.RECENT,
                            Memory.kind == MemoryKind.EPISODE,
                            Memory.sensitivity.in_(
                                [MemorySensitivity.PUBLIC, MemorySensitivity.INTERNAL]
                            ),
                            or_(Memory.valid_until.is_(None), Memory.valid_until > current),
                        )
                        .order_by(Memory.created_at.desc())
                        .limit(100)
                    )
                ).all()
            )
        if len(episodes) < 3:
            return None
        anchor = episodes[0]
        anchor_features = anchor.embedding_features or self.encoder.encode(anchor.content)
        cluster = [anchor]
        for episode in episodes[1:]:
            features = episode.embedding_features or self.encoder.encode(episode.content)
            if self.encoder.similarity(anchor_features, features) >= 0.30:
                cluster.append(episode)
        if len(cluster) < 3:
            return None
        ordered = sorted(cluster, key=lambda item: item.created_at)
        summaries = [item.summary or item.content for item in ordered]
        content = "近期反复出现的主题：" + "；".join(summaries[-5:])
        if len(content) > 2000:
            content = content[:1999] + "…"
        proposal = ExtractedMemory(
            content=content,
            summary=f"由 {len(cluster)} 条近期情景整理出的长期候选",
            kind=MemoryKind.FACT,
            lifecycle=MemoryLifecycle.DURABLE,
            sensitivity=MemorySensitivity.INTERNAL,
            policy_action=MemoryPolicyAction.CONFIRM,
            confidence=min(0.9, sum(item.confidence for item in cluster) / len(cluster)),
            importance=min(0.9, max(item.importance for item in cluster) + 0.15),
            policy_reason="repeated_recent_episodes_require_durable_confirmation",
        )
        return await self.record_candidate(
            user_id=user_id,
            actor_device_id=actor_device_id,
            proposal=proposal,
            source_session_id=anchor.source_session_id,
            source_message_id=anchor.source_message_id,
            request_id=request_id,
        )
