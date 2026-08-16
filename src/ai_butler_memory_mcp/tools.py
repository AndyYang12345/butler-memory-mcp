"""MCP tool definitions bound to :class:`MemoryOperations`.

The descriptions intentionally mirror the parent framework's
``memory_tools.py`` wording: writes happen only when the user explicitly
asks, never silently, and model-callable writes stay within the
public/internal sensitivity ceiling.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from .mcp_server import McpTool
from .operations import BridgeError, MemoryOperations, memory_kinds, candidate_statuses

_KINDS = list(memory_kinds())
_STATUSES = list(candidate_statuses())


def _uuid(value: Any, field: str) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError) as exc:
        raise BridgeError("invalid_request", f"{field} must be a valid UUID") from exc


def _int_bounded(value: Any, field: str, minimum: int, maximum: int, default: int) -> int:
    if value is None:
        return default
    try:
        number = int(value)
    except (ValueError, TypeError) as exc:
        raise BridgeError("invalid_request", f"{field} must be an integer") from exc
    if not minimum <= number <= maximum:
        raise BridgeError(
            "invalid_request", f"{field} must be between {minimum} and {maximum}"
        )
    return number


def build_tools(operations: MemoryOperations) -> list[McpTool]:
    async def list_memories(arguments: dict[str, Any]) -> dict[str, Any]:
        return await operations.list_memories(
            include_archived=bool(arguments.get("include_archived", False)),
            kind=arguments.get("kind"),
            limit=_int_bounded(arguments.get("limit"), "limit", 1, 100, 50),
        )

    async def search_memories(arguments: dict[str, Any]) -> dict[str, Any]:
        return await operations.search_memories(
            query=arguments.get("query"),
            kind=arguments.get("kind"),
            limit=_int_bounded(arguments.get("limit"), "limit", 1, 20, 10),
        )

    async def list_revisions(arguments: dict[str, Any]) -> dict[str, Any]:
        return await operations.list_revisions(
            memory_id=_uuid(arguments.get("memory_id"), "memory_id")
        )

    async def create_memory(arguments: dict[str, Any]) -> dict[str, Any]:
        return await operations.create_memory(
            content=arguments["content"],
            summary=arguments.get("summary"),
            kind=arguments.get("kind", "other"),
            sensitivity=arguments.get("sensitivity", "internal"),
        )

    async def revise_memory(arguments: dict[str, Any]) -> dict[str, Any]:
        return await operations.revise_memory(
            memory_id=_uuid(arguments.get("memory_id"), "memory_id"),
            expected_revision=_int_bounded(
                arguments.get("expected_revision"), "expected_revision", 1, 10_000, 1
            ),
            content=arguments["content"],
            summary=arguments.get("summary"),
            reason=arguments["reason"],
        )

    async def archive_memory(arguments: dict[str, Any]) -> dict[str, Any]:
        return await operations.archive_memory(
            memory_id=_uuid(arguments.get("memory_id"), "memory_id"),
            expected_revision=_int_bounded(
                arguments.get("expected_revision"), "expected_revision", 1, 10_000, 1
            ),
            reason=arguments["reason"],
        )

    async def list_candidates(arguments: dict[str, Any]) -> dict[str, Any]:
        return await operations.list_candidates(
            status=arguments.get("status"),
            limit=_int_bounded(arguments.get("limit"), "limit", 1, 100, 50),
        )

    async def accept_candidate(arguments: dict[str, Any]) -> dict[str, Any]:
        return await operations.accept_candidate(
            candidate_id=_uuid(arguments.get("candidate_id"), "candidate_id")
        )

    async def reject_candidate(arguments: dict[str, Any]) -> dict[str, Any]:
        return await operations.reject_candidate(
            candidate_id=_uuid(arguments.get("candidate_id"), "candidate_id")
        )

    return [
        McpTool(
            name="memory_list",
            description=(
                "List the user's durable memories. Include archived records only "
                "when the user asks to review forgotten items."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "include_archived": {"type": "boolean", "default": False},
                    "kind": {
                        "type": "string",
                        "enum": _KINDS,
                        "description": "Optional memory kind filter.",
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
            },
            handler=list_memories,
        ),
        McpTool(
            name="memory_search",
            description=(
                "Search the user's active public or internal memories. Use this "
                "before revising or archiving a memory when its ID or current "
                "revision is unknown. Private and secret memories are excluded."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "maxLength": 500},
                    "kind": {"type": "string", "enum": _KINDS},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
            },
            handler=search_memories,
        ),
        McpTool(
            name="memory_revisions",
            description=(
                "List the immutable revision history of one owned memory, oldest "
                "first. Each revision records who changed it and why."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string", "format": "uuid"},
                },
                "required": ["memory_id"],
            },
            handler=list_revisions,
        ),
        McpTool(
            name="memory_create",
            description=(
                "Create one durable memory only when the user explicitly asks to "
                "remember something. Do not infer or silently store memories. "
                "Model-callable writes are limited to public or internal "
                "sensitivity and require the user's request. Never use this tool "
                "for naming, language, tone, or formatting preferences; those are "
                "Framework-managed Persona fields."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "minLength": 1, "maxLength": 100000},
                    "summary": {"type": "string", "maxLength": 10000},
                    "kind": {"type": "string", "enum": _KINDS, "default": "other"},
                    "sensitivity": {
                        "type": "string",
                        "enum": ["public", "internal"],
                        "default": "internal",
                    },
                },
                "required": ["content"],
            },
            handler=create_memory,
        ),
        McpTool(
            name="memory_revise",
            description=(
                "Replace one owned active memory using its exact current revision. "
                "Search first if the memory ID or revision is unknown. This "
                "persistent change requires the user's explicit request."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string", "format": "uuid"},
                    "expected_revision": {"type": "integer", "minimum": 1},
                    "content": {"type": "string", "minLength": 1, "maxLength": 100000},
                    "summary": {"type": "string", "maxLength": 10000},
                    "reason": {"type": "string", "minLength": 1, "maxLength": 500},
                },
                "required": [
                    "memory_id",
                    "expected_revision",
                    "content",
                    "reason",
                ],
            },
            handler=revise_memory,
        ),
        McpTool(
            name="memory_archive",
            description=(
                "Forget one owned memory by archiving it with its exact current "
                "revision. Search first if the memory ID or revision is unknown. "
                "Archiving removes it from normal recall but preserves revision "
                "and audit history."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "memory_id": {"type": "string", "format": "uuid"},
                    "expected_revision": {"type": "integer", "minimum": 1},
                    "reason": {"type": "string", "minLength": 1, "maxLength": 500},
                },
                "required": ["memory_id", "expected_revision", "reason"],
            },
            handler=archive_memory,
        ),
        McpTool(
            name="memory_candidates",
            description=(
                "List inferred memory candidates that the Framework policy has not "
                "silently turned into long-term memory. Pending candidates wait "
                "for an explicit user decision."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": _STATUSES},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
            },
            handler=list_candidates,
        ),
        McpTool(
            name="memory_candidate_accept",
            description=(
                "Promote one pending memory candidate into durable memory after "
                "the user explicitly approves it."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string", "format": "uuid"},
                },
                "required": ["candidate_id"],
            },
            handler=accept_candidate,
        ),
        McpTool(
            name="memory_candidate_reject",
            description=(
                "Reject one pending memory candidate after the user explicitly "
                "declines it. The rejection is audited."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "candidate_id": {"type": "string", "format": "uuid"},
                },
                "required": ["candidate_id"],
            },
            handler=reject_candidate,
        ),
    ]
