"""Vendored from ai-butler-framework persistence/services.py: identity bootstrap slice."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy import select

from .credentials import issue_credential
from .database import Database
from .memory_service import _audit, _clean_text, _ensure_device_owner, ResourceNotFoundError
from .models import (
    DeliverySubscription,
    Device,
    DeviceCredential,
    User,
    UserStatus,
)
from .timezone import validate_timezone


_SCOPE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}:[a-z][a-z0-9_.-]{0,63}$")
DEFAULT_DEVICE_SCOPES = frozenset(
    {
        "chat:read",
        "chat:write",
        "memory:read",
        "memory:write",
        "calendar:read",
        "calendar:write",
        "settings:read",
        "settings:write",
    }
)
@dataclass(frozen=True, slots=True)
class BootstrapResult:
    user_id: UUID
    device_id: UUID
    credential_id: UUID
    token: SecretStr
    scopes: frozenset[str]
def _validated_scopes(scopes: set[str] | frozenset[str]) -> frozenset[str]:
    normalized = frozenset(scope.strip() for scope in scopes)
    if not normalized or any(not _SCOPE.fullmatch(scope) for scope in normalized):
        raise ValueError("Scopes must use resource:action names")
    return normalized
class IdentityService:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def bootstrap(
        self,
        *,
        user_display_name: str,
        device_name: str,
        device_kind: str = "local",
        timezone: str = "Asia/Shanghai",
        scopes: set[str] | frozenset[str] = DEFAULT_DEVICE_SCOPES,
        request_id: UUID | None = None,
    ) -> BootstrapResult:
        user_display_name = _clean_text(
            user_display_name, "user_display_name", maximum=200
        )
        device_name = _clean_text(device_name, "device_name", maximum=200)
        device_kind = _clean_text(device_kind, "device_kind", maximum=50)
        validate_timezone(timezone)
        validated_scopes = _validated_scopes(scopes)
        issued = issue_credential()
        user_id = uuid4()
        device_id = uuid4()

        async with self.database.session() as session:
            session.add(
                User(
                    id=user_id,
                    display_name=user_display_name,
                    default_timezone=timezone,
                )
            )
            await session.flush()
            session.add(
                Device(
                    id=device_id,
                    user_id=user_id,
                    name=device_name,
                    kind=device_kind,
                    timezone=timezone,
                )
            )
            await session.flush()
            session.add(
                DeviceCredential(
                    id=issued.credential_id,
                    device_id=device_id,
                    token_digest=issued.token_digest,
                    token_hint=issued.token_hint,
                    scopes=sorted(validated_scopes),
                )
            )
            session.add(
                DeliverySubscription(
                    user_id=user_id,
                    device_id=device_id,
                    channel="client.poll.v1",
                    enabled=True,
                    priority=0,
                )
            )
            # These models intentionally have no ORM relationships. Flush each
            # dependency in foreign-key order while retaining one transaction.
            await session.flush()
            _audit(
                session,
                action="identity.bootstrap",
                resource_type="device",
                resource_id=device_id,
                actor_user_id=user_id,
                actor_device_id=device_id,
                request_id=request_id,
                metadata={"credential_id": str(issued.credential_id)},
            )

        return BootstrapResult(
            user_id=user_id,
            device_id=device_id,
            credential_id=issued.credential_id,
            token=issued.token,
            scopes=validated_scopes,
        )

    async def add_device(
        self,
        *,
        user_id: UUID,
        device_name: str,
        device_kind: str = "personal",
        timezone: str = "Asia/Shanghai",
        scopes: set[str] | frozenset[str] = DEFAULT_DEVICE_SCOPES,
        actor_device_id: UUID | None = None,
        request_id: UUID | None = None,
    ) -> BootstrapResult:
        """Register another device for an existing active user.

        This is a local administrator operation. The returned bearer token is a
        one-time secret and only its digest is persisted.
        """

        device_name = _clean_text(device_name, "device_name", maximum=200)
        device_kind = _clean_text(device_kind, "device_kind", maximum=50)
        validate_timezone(timezone)
        validated_scopes = _validated_scopes(scopes)
        issued = issue_credential()
        device_id = uuid4()

        async with self.database.session() as session:
            user = await session.scalar(
                select(User)
                .where(User.id == user_id, User.status == UserStatus.ACTIVE)
                .with_for_update()
            )
            if user is None:
                raise ResourceNotFoundError("Active user does not exist")
            if actor_device_id is not None:
                await _ensure_device_owner(session, user_id, actor_device_id)
            session.add(
                Device(
                    id=device_id,
                    user_id=user_id,
                    name=device_name,
                    kind=device_kind,
                    timezone=timezone,
                )
            )
            await session.flush()
            session.add(
                DeviceCredential(
                    id=issued.credential_id,
                    device_id=device_id,
                    token_digest=issued.token_digest,
                    token_hint=issued.token_hint,
                    scopes=sorted(validated_scopes),
                )
            )
            session.add(
                DeliverySubscription(
                    user_id=user_id,
                    device_id=device_id,
                    channel="client.poll.v1",
                    enabled=True,
                    priority=0,
                )
            )
            await session.flush()
            _audit(
                session,
                action="identity.device.register",
                resource_type="device",
                resource_id=device_id,
                actor_user_id=user_id,
                actor_device_id=actor_device_id,
                request_id=request_id,
                metadata={"credential_id": str(issued.credential_id)},
            )

        return BootstrapResult(
            user_id=user_id,
            device_id=device_id,
            credential_id=issued.credential_id,
            token=issued.token,
            scopes=validated_scopes,
        )
