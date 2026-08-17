"""Opaque device bearer credentials; plaintext tokens are never persisted."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from uuid import UUID, uuid4

from pydantic import SecretStr

_TOKEN_PREFIX = "aib"
_SECRET_BYTES = 32


class MalformedCredentialError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IssuedCredential:
    credential_id: UUID
    token: SecretStr
    token_digest: bytes
    token_hint: str


def issue_credential() -> IssuedCredential:
    credential_id = uuid4()
    secret = secrets.token_urlsafe(_SECRET_BYTES)
    token = f"{_TOKEN_PREFIX}_{credential_id.hex}_{secret}"
    return IssuedCredential(
        credential_id=credential_id,
        token=SecretStr(token),
        token_digest=digest_credential(token),
        token_hint=secret[-6:],
    )


def credential_id_from_token(token: str) -> UUID:
    if len(token) > 200:
        raise MalformedCredentialError("Invalid device credential")
    parts = token.split("_", maxsplit=2)
    if len(parts) != 3 or parts[0] != _TOKEN_PREFIX or len(parts[2]) < 40:
        raise MalformedCredentialError("Invalid device credential")
    try:
        return UUID(hex=parts[1])
    except ValueError as exc:
        raise MalformedCredentialError("Invalid device credential") from exc


def digest_credential(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()
