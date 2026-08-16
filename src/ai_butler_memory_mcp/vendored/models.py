"""Initial durable schema for identity, conversations, memory, and audit."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Float,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(UTC)


NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class DeviceStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class PluginPackageStatus(StrEnum):
    INSTALLED = "installed"
    FAILED = "failed"
    REMOVED = "removed"


class ChatSessionStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ChatMessageRole(StrEnum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class MemoryKind(StrEnum):
    FACT = "fact"
    PREFERENCE = "preference"
    PROJECT = "project"
    ROUTINE = "routine"
    EPISODE = "episode"
    OTHER = "other"


class MemorySensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    PRIVATE = "private"
    SECRET = "secret"


class MemoryStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class MemoryWriteMode(StrEnum):
    EXPLICIT = "explicit"
    AUTOMATIC = "automatic"
    IMPORTED = "imported"


class MemoryLifecycle(StrEnum):
    RECENT = "recent"
    DURABLE = "durable"


class MemoryCandidateStatus(StrEnum):
    PENDING = "pending"
    AUTO_STORED = "auto_stored"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class MemoryPolicyAction(StrEnum):
    AUTO_STORE = "auto_store"
    NOTIFY_UNDO = "notify_undo"
    CONFIRM = "confirm"
    REJECT = "reject"


class PersonaResponseLength(StrEnum):
    CONCISE = "concise"
    BALANCED = "balanced"
    DETAILED = "detailed"


class PersonaTone(StrEnum):
    NEUTRAL = "neutral"
    GENTLE = "gentle"
    DIRECT = "direct"
    WARM = "warm"


class PersonaTechnicalDepth(StrEnum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class PersonaFormatPreference(StrEnum):
    MINIMAL = "minimal"
    STRUCTURED = "structured"
    RICH_MARKDOWN = "rich_markdown"


class FrameworkNotificationStatus(StrEnum):
    UNREAD = "unread"
    READ = "read"
    REVERTED = "reverted"


class ProviderBudgetEnforcement(StrEnum):
    OBSERVE = "observe"
    BLOCK = "block"


class MemoryEvidenceType(StrEnum):
    USER_STATEMENT = "user_statement"
    CONVERSATION = "conversation"
    TOOL_RESULT = "tool_result"
    IMPORT = "import"


class ToolConfirmationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CONSUMED = "consumed"


class ToolInvocationDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    CONFIRM = "confirm"


class ToolInvocationStatus(StrEnum):
    REQUESTED = "requested"
    DENIED = "denied"
    CONFIRMATION_REQUIRED = "confirmation_required"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class ToolIdempotencyState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMMITTED = "committed"
    FAILED = "failed"
    INDETERMINATE = "indeterminate"


class ToolExecutionIntentStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INDETERMINATE = "indeterminate"
    EXPIRED = "expired"


class ToolExecutionIntentPayloadKind(StrEnum):
    CALL = "call"
    RESULT = "result"


class SuspendedTurnStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    INDETERMINATE = "indeterminate"


class CalendarEventStatus(StrEnum):
    ACTIVE = "active"
    CANCELLED = "cancelled"


class CalendarTemporalKind(StrEnum):
    POINT = "point"
    INTERVAL = "interval"
    DEADLINE = "deadline"
    ALL_DAY = "all_day"


class ReminderStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class ReminderTriggerType(StrEnum):
    TIME = "time"
    LOCATION = "location"
    CONTEXT = "context"


class ReminderDeliveryStrategy(StrEnum):
    AUTO_PRIORITY = "auto_priority"
    SELECTED_DEVICES = "selected_devices"
    ALL_DEVICES = "all_devices"


class DevicePresenceState(StrEnum):
    UNKNOWN = "unknown"
    PRESENT = "present"
    ABSENT = "absent"


class ReminderDeliveryStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    ACKNOWLEDGED = "acknowledged"
    SUPPRESSED = "suppressed"


class ReminderOccurrenceStatus(StrEnum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"


def enum_column(enum_type: type[StrEnum], name: str) -> Enum:
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=lambda members: [member.value for member in members],
    )


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
        nullable=False,
    )


class User(Timestamped, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    default_timezone: Mapped[str] = mapped_column(
        String(255), default="Asia/Shanghai", nullable=False
    )
    status: Mapped[UserStatus] = mapped_column(
        enum_column(UserStatus, "user_status"), default=UserStatus.ACTIVE, nullable=False
    )


class Device(Timestamped, Base):
    __tablename__ = "devices"
    __table_args__ = (Index("ix_devices_user_status", "user_id", "status"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(255), default="Asia/Shanghai", nullable=False
    )
    status: Mapped[DeviceStatus] = mapped_column(
        enum_column(DeviceStatus, "device_status"),
        default=DeviceStatus.ACTIVE,
        nullable=False,
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeviceCredential(Base):
    __tablename__ = "device_credentials"
    __table_args__ = (
        CheckConstraint(
            "expires_at IS NULL OR expires_at > created_at",
            name="expires_after_creation",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_digest: Mapped[bytes] = mapped_column(
        LargeBinary(32), nullable=False, unique=True
    )
    token_hint: Mapped[str] = mapped_column(String(12), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BrowserSession(Base):
    __tablename__ = "browser_sessions"
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="expires_after_creation"),
        Index(
            "ix_browser_sessions_device_active",
            "device_id",
            "revoked_at",
            "expires_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    credential_id: Mapped[UUID] = mapped_column(
        ForeignKey("device_credentials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_digest: Mapped[bytes] = mapped_column(
        LargeBinary(32), nullable=False, unique=True
    )
    token_hint: Mapped[str] = mapped_column(String(12), nullable=False)
    remember_device: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChatSession(Timestamped, Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("ix_chat_sessions_user_activity", "user_id", "last_activity_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ChatSessionStatus] = mapped_column(
        enum_column(ChatSessionStatus, "chat_session_status"),
        default=ChatSessionStatus.ACTIVE,
        nullable=False,
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        UniqueConstraint("session_id", "position"),
        CheckConstraint("position >= 0", name="nonnegative_position"),
        Index("ix_chat_messages_session_created", "session_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[ChatMessageRole] = mapped_column(
        enum_column(ChatMessageRole, "chat_message_role"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    provider_id: Mapped[str | None] = mapped_column(String(100))
    model_id: Mapped[str | None] = mapped_column(String(200))
    trace_id: Mapped[UUID | None] = mapped_column(Uuid)
    turn_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )


class ToolCatalogSnapshotRecord(Base):
    """Immutable, secret-free Tool Catalog bound to one conversation Turn."""

    __tablename__ = "tool_catalog_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "turn_id",
            name="uq_tool_catalog_snapshots_session_turn",
        ),
        CheckConstraint("tool_count >= 0", name="nonnegative_tool_count"),
        Index(
            "ix_tool_catalog_snapshots_user_created",
            "user_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    trace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    turn_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    catalog_version: Mapped[str] = mapped_column(String(20), nullable=False)
    catalog_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    tool_count: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )


class SkillPreference(Timestamped, Base):
    __tablename__ = "skill_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "skill_id",
            name="uq_skill_preferences_user_skill",
        ),
        CheckConstraint("current_revision >= 1", name="positive_revision"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    current_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class SkillPreferenceRevision(Base):
    __tablename__ = "skill_preference_revisions"
    __table_args__ = (
        UniqueConstraint(
            "preference_id",
            "revision",
            name="uq_skill_preference_revisions_preference_revision",
        ),
        CheckConstraint("revision >= 1", name="positive_revision"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    preference_id: Mapped[UUID] = mapped_column(
        ForeignKey("skill_preferences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )


class McpServerPreference(Timestamped, Base):
    __tablename__ = "mcp_server_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "server_id",
            name="uq_mcp_server_preferences_user_server",
        ),
        CheckConstraint("current_revision >= 1", name="positive_revision"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    server_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    current_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class McpServerPreferenceRevision(Base):
    __tablename__ = "mcp_server_preference_revisions"
    __table_args__ = (
        UniqueConstraint(
            "preference_id",
            "revision",
            name="uq_mcp_server_preference_revisions_preference_revision",
        ),
        CheckConstraint("revision >= 1", name="positive_revision"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    preference_id: Mapped[UUID] = mapped_column(
        ForeignKey("mcp_server_preferences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )


class SkillTurnSnapshotRecord(Base):
    __tablename__ = "skill_turn_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "turn_id",
            name="uq_skill_turn_snapshots_session_turn",
        ),
        CheckConstraint("skill_count >= 0", name="nonnegative_skill_count"),
        Index("ix_skill_turn_snapshots_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    trace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    turn_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    snapshot_version: Mapped[str] = mapped_column(String(20), nullable=False)
    snapshot_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    skill_count: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evaluations: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )


class Memory(Timestamped, Base):
    __tablename__ = "memories"
    __table_args__ = (
        CheckConstraint("current_revision >= 1", name="positive_revision"),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="bounded_confidence"
        ),
        CheckConstraint(
            "importance >= 0 AND importance <= 1", name="bounded_importance"
        ),
        Index("ix_memories_user_status_kind", "user_id", "status", "kind"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[MemoryKind] = mapped_column(
        enum_column(MemoryKind, "memory_kind"), nullable=False
    )
    sensitivity: Mapped[MemorySensitivity] = mapped_column(
        enum_column(MemorySensitivity, "memory_sensitivity"), nullable=False
    )
    status: Mapped[MemoryStatus] = mapped_column(
        enum_column(MemoryStatus, "memory_status"),
        default=MemoryStatus.ACTIVE,
        nullable=False,
    )
    write_mode: Mapped[MemoryWriteMode] = mapped_column(
        enum_column(MemoryWriteMode, "memory_write_mode"), nullable=False
    )
    lifecycle: Mapped[MemoryLifecycle] = mapped_column(
        enum_column(MemoryLifecycle, "memory_lifecycle"),
        default=MemoryLifecycle.DURABLE,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    importance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    embedding_features: Mapped[dict[str, float] | None] = mapped_column(JSON)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    access_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL")
    )
    source_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL")
    )
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MemoryRevision(Base):
    __tablename__ = "memory_revisions"
    __table_args__ = (
        UniqueConstraint("memory_id", "revision"),
        CheckConstraint("revision >= 1", name="positive_revision"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    memory_id: Mapped[UUID] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )


class MemoryEvidence(Base):
    __tablename__ = "memory_evidence"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    memory_id: Mapped[UUID] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_type: Mapped[MemoryEvidenceType] = mapped_column(
        enum_column(MemoryEvidenceType, "memory_evidence_type"), nullable=False
    )
    source_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL")
    )
    source_reference: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )


class MemoryCandidate(Timestamped, Base):
    __tablename__ = "memory_candidates"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "fingerprint", name="uq_memory_candidates_user_fingerprint"
        ),
        CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="bounded_confidence"
        ),
        CheckConstraint(
            "importance >= 0 AND importance <= 1", name="bounded_importance"
        ),
        Index(
            "ix_memory_candidates_user_status_created",
            "user_id",
            "status",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_device_id: Mapped[UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL")
    )
    source_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL")
    )
    kind: Mapped[MemoryKind] = mapped_column(
        enum_column(MemoryKind, "memory_candidate_kind"), nullable=False
    )
    lifecycle: Mapped[MemoryLifecycle] = mapped_column(
        enum_column(MemoryLifecycle, "memory_candidate_lifecycle"), nullable=False
    )
    sensitivity: Mapped[MemorySensitivity] = mapped_column(
        enum_column(MemorySensitivity, "memory_candidate_sensitivity"),
        nullable=False,
    )
    policy_action: Mapped[MemoryPolicyAction] = mapped_column(
        enum_column(MemoryPolicyAction, "memory_policy_action"), nullable=False
    )
    status: Mapped[MemoryCandidateStatus] = mapped_column(
        enum_column(MemoryCandidateStatus, "memory_candidate_status"),
        default=MemoryCandidateStatus.PENDING,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    importance: Mapped[float] = mapped_column(Float, nullable=False)
    policy_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    matched_memory_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("memories.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PersonaProfile(Timestamped, Base):
    __tablename__ = "persona_profiles"
    __table_args__ = (
        CheckConstraint("current_revision >= 1", name="positive_revision"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    preferred_language: Mapped[str] = mapped_column(
        String(35), default="zh-CN", nullable=False
    )
    address_name: Mapped[str | None] = mapped_column(String(100))
    assistant_display_name: Mapped[str | None] = mapped_column(String(100))
    response_length: Mapped[PersonaResponseLength] = mapped_column(
        enum_column(PersonaResponseLength, "persona_response_length"),
        default=PersonaResponseLength.BALANCED,
        nullable=False,
    )
    tone: Mapped[PersonaTone] = mapped_column(
        enum_column(PersonaTone, "persona_tone"),
        default=PersonaTone.NEUTRAL,
        nullable=False,
    )
    technical_depth: Mapped[PersonaTechnicalDepth] = mapped_column(
        enum_column(PersonaTechnicalDepth, "persona_technical_depth"),
        default=PersonaTechnicalDepth.INTERMEDIATE,
        nullable=False,
    )
    format_preference: Mapped[PersonaFormatPreference] = mapped_column(
        enum_column(PersonaFormatPreference, "persona_format_preference"),
        default=PersonaFormatPreference.STRUCTURED,
        nullable=False,
    )
    current_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class PersonaRevision(Base):
    __tablename__ = "persona_revisions"
    __table_args__ = (
        UniqueConstraint("profile_id", "revision"),
        CheckConstraint("revision >= 1", name="positive_revision"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("persona_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    changed_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL")
    )
    source_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )


class PluginPackage(Base):
    """One immutable, content-addressed locally installed Plugin version."""

    __tablename__ = "plugin_packages"
    __table_args__ = (
        UniqueConstraint("plugin_id", "version", name="uq_plugin_packages_id_version"),
        UniqueConstraint("package_digest", name="uq_plugin_packages_digest"),
        Index("ix_plugin_packages_id_status", "plugin_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    plugin_id: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    package_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(1_024), nullable=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    permission_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    status: Mapped[PluginPackageStatus] = mapped_column(
        enum_column(PluginPackageStatus, "plugin_package_status"),
        default=PluginPackageStatus.INSTALLED,
        nullable=False,
    )
    installed_by: Mapped[str] = mapped_column(String(200), nullable=False)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )


class PluginInstallation(Timestamped, Base):
    """Global local-admin activation pointer and approved permission snapshot."""

    __tablename__ = "plugin_installations"
    __table_args__ = (
        CheckConstraint("current_revision >= 0", name="nonnegative_revision"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    plugin_id: Mapped[str] = mapped_column(
        String(200), nullable=False, unique=True, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active_package_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("plugin_packages.id", ondelete="RESTRICT"), index=True
    )
    approved_permissions: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    current_revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_retained: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PluginInstallationRevision(Base):
    __tablename__ = "plugin_installation_revisions"
    __table_args__ = (
        UniqueConstraint("installation_id", "revision"),
        CheckConstraint("revision >= 1", name="positive_revision"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    installation_id: Mapped[UUID] = mapped_column(
        ForeignKey("plugin_installations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    actor: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )


class PluginHealthEvent(Base):
    __tablename__ = "plugin_health_events"
    __table_args__ = (
        Index("ix_plugin_health_package_created", "package_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("plugin_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    message_code: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )


class ProviderProfile(Timestamped, Base):
    """User-owned default model Provider selection without deployment secrets."""

    __tablename__ = "provider_profiles"
    __table_args__ = (
        CheckConstraint("current_revision >= 1", name="positive_revision"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    default_provider_id: Mapped[str] = mapped_column(String(100), nullable=False)
    default_model_id: Mapped[str | None] = mapped_column(String(200))
    current_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ProviderProfileRevision(Base):
    __tablename__ = "provider_profile_revisions"
    __table_args__ = (
        UniqueConstraint("profile_id", "revision"),
        CheckConstraint("revision >= 1", name="positive_revision"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    changed_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )


class ProviderUsageRecord(Base):
    """One immutable, provider-neutral usage fact for a completed Turn."""

    __tablename__ = "provider_usage_records"
    __table_args__ = (
        Index("ix_provider_usage_user_occurred", "user_id", "occurred_at"),
        Index(
            "ix_provider_usage_user_provider_occurred",
            "user_id",
            "provider_id",
            "occurred_at",
        ),
        CheckConstraint("input_tokens >= 0", name="nonnegative_input_tokens"),
        CheckConstraint("output_tokens >= 0", name="nonnegative_output_tokens"),
        CheckConstraint("total_tokens >= 0", name="nonnegative_total_tokens"),
        CheckConstraint(
            "cache_read_input_tokens >= 0",
            name="nonnegative_cache_read_input_tokens",
        ),
        CheckConstraint(
            "provider_attempt_count >= 1",
            name="positive_provider_attempt_count",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL")
    )
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL")
    )
    assistant_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL")
    )
    turn_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, unique=True)
    provider_id: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(50), nullable=False)
    model_id: Mapped[str] = mapped_column(String(200), nullable=False)
    usage_available: Mapped[bool] = mapped_column(Boolean, nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    cache_read_input_tokens: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    cache_miss_input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    reasoning_tokens: Mapped[int | None] = mapped_column(BigInteger)
    estimated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider_attempt_count: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    fallback_from_provider_id: Mapped[str | None] = mapped_column(String(100))
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )


class ProviderBudgetProfile(Timestamped, Base):
    __tablename__ = "provider_budget_profiles"
    __table_args__ = (
        CheckConstraint("current_revision >= 1", name="positive_revision"),
        CheckConstraint(
            "monthly_total_token_limit IS NULL OR monthly_total_token_limit > 0",
            name="positive_monthly_total_token_limit",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    enforcement: Mapped[ProviderBudgetEnforcement] = mapped_column(
        enum_column(ProviderBudgetEnforcement, "provider_budget_enforcement"),
        default=ProviderBudgetEnforcement.OBSERVE,
        nullable=False,
    )
    monthly_total_token_limit: Mapped[int | None] = mapped_column(BigInteger)
    provider_monthly_token_limits: Mapped[dict[str, int]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    current_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ProviderBudgetRevision(Base):
    __tablename__ = "provider_budget_revisions"
    __table_args__ = (
        UniqueConstraint("profile_id", "revision"),
        CheckConstraint("revision >= 1", name="positive_revision"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider_budget_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    changed_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )


class ProviderReliabilityProfile(Timestamped, Base):
    __tablename__ = "provider_reliability_profiles"
    __table_args__ = (
        CheckConstraint("current_revision >= 1", name="positive_revision"),
        CheckConstraint(
            "max_provider_attempts >= 1 AND max_provider_attempts <= 4",
            name="valid_max_provider_attempts",
        ),
        CheckConstraint(
            "retry_initial_delay_ms >= 0 AND retry_initial_delay_ms <= 5000",
            name="valid_retry_initial_delay_ms",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    max_provider_attempts: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )
    retry_initial_delay_ms: Mapped[int] = mapped_column(
        Integer, default=250, nullable=False
    )
    fallback_provider_ids: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    current_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ProviderReliabilityRevision(Base):
    __tablename__ = "provider_reliability_revisions"
    __table_args__ = (
        UniqueConstraint("profile_id", "revision"),
        CheckConstraint("revision >= 1", name="positive_revision"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("provider_reliability_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    changed_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    actor_device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )


class FrameworkNotification(Timestamped, Base):
    __tablename__ = "framework_notifications"
    __table_args__ = (
        Index(
            "ix_framework_notifications_user_status_created",
            "user_id",
            "status",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[FrameworkNotificationStatus] = mapped_column(
        enum_column(FrameworkNotificationStatus, "framework_notification_status"),
        default=FrameworkNotificationStatus.UNREAD,
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(String(1000), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    from_revision: Mapped[int | None] = mapped_column(Integer)
    to_revision: Mapped[int | None] = mapped_column(Integer)
    event_data: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reverted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CalendarEvent(Timestamped, Base):
    __tablename__ = "calendar_events"
    __table_args__ = (
        CheckConstraint("revision >= 1", name="positive_revision"),
        CheckConstraint(
            "end_at_utc IS NULL OR start_at_utc IS NULL OR end_at_utc > start_at_utc",
            name="end_after_start",
        ),
        CheckConstraint(
            "all_day_end_date IS NULL OR all_day_start_date IS NULL "
            "OR all_day_end_date > all_day_start_date",
            name="all_day_end_after_start",
        ),
        CheckConstraint(
            "location_latitude IS NULL OR "
            "(location_latitude >= -90 AND location_latitude <= 90)",
            name="valid_latitude",
        ),
        CheckConstraint(
            "location_longitude IS NULL OR "
            "(location_longitude >= -180 AND location_longitude <= 180)",
            name="valid_longitude",
        ),
        Index(
            "ix_calendar_events_user_status_time",
            "user_id",
            "status",
            "start_at_utc",
            "due_at_utc",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    source_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    temporal_kind: Mapped[CalendarTemporalKind] = mapped_column(
        enum_column(CalendarTemporalKind, "calendar_temporal_kind"), nullable=False
    )
    timezone: Mapped[str] = mapped_column(String(255), nullable=False)
    start_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    all_day_start_date: Mapped[date | None] = mapped_column(Date)
    all_day_end_date: Mapped[date | None] = mapped_column(Date)
    recurrence_rule: Mapped[str | None] = mapped_column(String(1000))
    location_name: Mapped[str | None] = mapped_column(String(500))
    location_address: Mapped[str | None] = mapped_column(String(1000))
    location_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    location_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    status: Mapped[CalendarEventStatus] = mapped_column(
        enum_column(CalendarEventStatus, "calendar_event_status"),
        default=CalendarEventStatus.ACTIVE,
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CalendarEventParticipant(Base):
    __tablename__ = "calendar_event_participants"
    __table_args__ = (
        UniqueConstraint("event_id", "position"),
        CheckConstraint("position >= 0", name="nonnegative_position"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    role: Mapped[str | None] = mapped_column(String(200))


class CalendarEventRequirement(Base):
    __tablename__ = "calendar_event_requirements"
    __table_args__ = (
        UniqueConstraint("event_id", "position"),
        CheckConstraint("position >= 0", name="nonnegative_position"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)


class ReminderRule(Timestamped, Base):
    __tablename__ = "reminder_rules"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "operation_key", name="uq_reminder_rules_user_operation"
        ),
        CheckConstraint("revision >= 1", name="positive_revision"),
        CheckConstraint("cooldown_seconds >= 0", name="nonnegative_cooldown"),
        CheckConstraint("fire_count >= 0", name="nonnegative_fire_count"),
        CheckConstraint(
            "max_firings IS NULL OR max_firings >= 1", name="positive_max_firings"
        ),
        Index(
            "ix_reminder_rules_user_status_next_trigger",
            "user_id",
            "status",
            "next_trigger_at_utc",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("calendar_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    trigger_type: Mapped[ReminderTriggerType] = mapped_column(
        enum_column(ReminderTriggerType, "reminder_trigger_type"), nullable=False
    )
    trigger_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    trigger_config: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    delivery_strategy: Mapped[ReminderDeliveryStrategy] = mapped_column(
        enum_column(ReminderDeliveryStrategy, "reminder_delivery_strategy"),
        default=ReminderDeliveryStrategy.AUTO_PRIORITY,
        nullable=False,
    )
    target_device_ids: Mapped[list[str]] = mapped_column(
        JSON, default=list, nullable=False
    )
    next_trigger_at_utc: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_firings: Mapped[int | None] = mapped_column(Integer)
    fire_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ReminderStatus] = mapped_column(
        enum_column(ReminderStatus, "reminder_status"),
        default=ReminderStatus.ACTIVE,
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    operation_key: Mapped[str] = mapped_column(String(255), nullable=False)
    operation_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeliverySubscription(Timestamped, Base):
    """Durable device preference for one versioned delivery channel."""

    __tablename__ = "delivery_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "device_id", "channel", name="uq_delivery_subscriptions_device_channel"
        ),
        Index(
            "ix_delivery_subscriptions_user_channel_enabled",
            "user_id",
            "channel",
            "enabled",
        ),
        CheckConstraint(
            "priority >= -10000 AND priority <= 10000", name="bounded_priority"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    presence_state: Mapped[DevicePresenceState] = mapped_column(
        enum_column(DevicePresenceState, "device_presence_state"),
        default=DevicePresenceState.UNKNOWN,
        nullable=False,
    )
    presence_observed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    presence_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReminderOccurrence(Timestamped, Base):
    """One logical reminder firing shared by all device deliveries."""

    __tablename__ = "reminder_occurrences"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "occurrence_key", name="uq_reminder_occurrences_user_key"
        ),
        Index(
            "ix_reminder_occurrences_user_status_schedule",
            "user_id",
            "status",
            "scheduled_for_utc",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reminder_id: Mapped[UUID] = mapped_column(
        ForeignKey("reminder_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    occurrence_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[ReminderOccurrenceStatus] = mapped_column(
        enum_column(ReminderOccurrenceStatus, "reminder_occurrence_status"),
        default=ReminderOccurrenceStatus.PENDING,
        nullable=False,
    )
    scheduled_for_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by_device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )


class ReminderDelivery(Timestamped, Base):
    __tablename__ = "reminder_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "deduplication_key", name="uq_reminder_deliveries_user_dedup"
        ),
        CheckConstraint("attempt >= 0", name="nonnegative_attempt"),
        Index(
            "ix_reminder_deliveries_status_schedule",
            "status",
            "scheduled_for_utc",
        ),
        UniqueConstraint(
            "occurrence_id",
            "target_device_id",
            "channel",
            name="uq_reminder_deliveries_occurrence_target_channel",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reminder_id: Mapped[UUID] = mapped_column(
        ForeignKey("reminder_rules.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    occurrence_id: Mapped[UUID] = mapped_column(
        ForeignKey("reminder_occurrences.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscription_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("delivery_subscriptions.id", ondelete="SET NULL"), index=True
    )
    target_device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    context_event_id: Mapped[str | None] = mapped_column(String(255))
    channel: Mapped[str] = mapped_column(String(100), nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[ReminderDeliveryStatus] = mapped_column(
        enum_column(ReminderDeliveryStatus, "reminder_delivery_status"),
        default=ReminderDeliveryStatus.PENDING,
        nullable=False,
    )
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scheduled_for_utc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    actor_device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(200), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(Uuid)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    request_id: Mapped[UUID | None] = mapped_column(Uuid, index=True)
    event_data: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=func.now(), nullable=False
    )


class ToolConfirmationRecord(Timestamped, Base):
    __tablename__ = "tool_confirmations"
    __table_args__ = (
        UniqueConstraint(
            "request_id",
            "tool_call_id",
            name="uq_tool_confirmations_request_tool_call",
        ),
        UniqueConstraint(
            "user_id",
            "tool_name",
            "idempotency_key",
            name="uq_tool_confirmations_idempotency",
        ),
        CheckConstraint("expires_at > created_at", name="expires_after_creation"),
        Index("ix_tool_confirmations_principal_status", "user_id", "device_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"), index=True
    )
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    trace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    turn_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    tool_call_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    arguments_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    status: Mapped[ToolConfirmationStatus] = mapped_column(
        enum_column(ToolConfirmationStatus, "tool_confirmation_status"),
        default=ToolConfirmationStatus.PENDING,
        nullable=False,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ToolIdempotencyRecord(Timestamped, Base):
    __tablename__ = "tool_idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "tool_name",
            "idempotency_key",
            name="uq_tool_idempotency_principal_tool_key",
        ),
        UniqueConstraint(
            "confirmation_id",
            name="uq_tool_idempotency_confirmation",
        ),
        CheckConstraint("attempt >= 0", name="nonnegative_attempt"),
        Index(
            "ix_tool_idempotency_state_lease",
            "state",
            "lease_expires_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    confirmation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tool_confirmations.id", ondelete="SET NULL"), index=True
    )
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    arguments_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    state: Mapped[ToolIdempotencyState] = mapped_column(
        enum_column(ToolIdempotencyState, "tool_idempotency_state"),
        default=ToolIdempotencyState.PENDING,
        nullable=False,
    )
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_digest: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    error_code: Mapped[str | None] = mapped_column(String(100))


class ToolExecutionIntent(Timestamped, Base):
    __tablename__ = "tool_execution_intents"
    __table_args__ = (
        UniqueConstraint(
            "confirmation_id",
            name="uq_tool_execution_intents_confirmation",
        ),
        CheckConstraint("expires_at > created_at", name="expires_after_creation"),
        CheckConstraint("attempt >= 0", name="nonnegative_attempt"),
        Index(
            "ix_tool_execution_intents_principal_status",
            "user_id",
            "device_id",
            "status",
        ),
        Index(
            "ix_tool_execution_intents_status_lease",
            "status",
            "lease_expires_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    confirmation_id: Mapped[UUID] = mapped_column(
        ForeignKey("tool_confirmations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"), index=True
    )
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    trace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    turn_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    client_timezone: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_call_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(String(200), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(100), nullable=False)
    definition_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    arguments_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    payload_kind: Mapped[ToolExecutionIntentPayloadKind] = mapped_column(
        enum_column(ToolExecutionIntentPayloadKind, "tool_execution_intent_payload_kind"),
        default=ToolExecutionIntentPayloadKind.CALL,
        nullable=False,
    )
    payload_nonce: Mapped[bytes] = mapped_column(LargeBinary(12), nullable=False)
    payload_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    payload_key_id: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[ToolExecutionIntentStatus] = mapped_column(
        enum_column(ToolExecutionIntentStatus, "tool_execution_intent_status"),
        default=ToolExecutionIntentStatus.PENDING,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_digest: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    error_code: Mapped[str | None] = mapped_column(String(100))


class SuspendedChatTurn(Timestamped, Base):
    __tablename__ = "suspended_chat_turns"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "turn_id",
            name="uq_suspended_chat_turns_session_turn",
        ),
        UniqueConstraint(
            "current_confirmation_id",
            name="uq_suspended_chat_turns_confirmation",
        ),
        CheckConstraint("attempt >= 0", name="nonnegative_attempt"),
        Index(
            "ix_suspended_chat_turns_principal_status",
            "user_id",
            "device_id",
            "status",
        ),
        Index(
            "ix_suspended_chat_turns_status_lease",
            "status",
            "lease_expires_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    current_confirmation_id: Mapped[UUID] = mapped_column(
        ForeignKey("tool_confirmations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    trace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    turn_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    pending_tool_call_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_nonce: Mapped[bytes] = mapped_column(LargeBinary(12), nullable=False)
    payload_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    payload_key_id: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[SuspendedTurnStatus] = mapped_column(
        enum_column(SuspendedTurnStatus, "suspended_turn_status"),
        default=SuspendedTurnStatus.PENDING,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    final_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_messages.id", ondelete="SET NULL"), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))


class ToolInvocation(Timestamped, Base):
    __tablename__ = "tool_invocations"
    __table_args__ = (
        UniqueConstraint(
            "request_id",
            "tool_call_id",
            "attempt",
            name="uq_tool_invocations_request_tool_call_attempt",
        ),
        CheckConstraint("attempt >= 1", name="positive_attempt"),
        Index("ix_tool_invocations_principal_created", "user_id", "device_id", "created_at"),
        Index("ix_tool_invocations_tool_created", "tool_name", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    device_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL"), index=True
    )
    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"), index=True
    )
    confirmation_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tool_confirmations.id", ondelete="SET NULL"), index=True
    )
    idempotency_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tool_idempotency_records.id", ondelete="SET NULL"), index=True
    )
    request_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    trace_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    turn_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    tool_call_id: Mapped[str] = mapped_column(String(255), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(2), nullable=False)
    required_scopes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    arguments_digest: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    decision: Mapped[ToolInvocationDecision | None] = mapped_column(
        enum_column(ToolInvocationDecision, "tool_invocation_decision")
    )
    status: Mapped[ToolInvocationStatus] = mapped_column(
        enum_column(ToolInvocationStatus, "tool_invocation_status"),
        default=ToolInvocationStatus.REQUESTED,
        nullable=False,
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    result_digest: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
