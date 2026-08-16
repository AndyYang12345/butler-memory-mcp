"""Loopback HTTP API for the DSH memory panel.

The MCP stdio surface serves the MODEL. This surface serves the WEB PANEL:
the DSH host plugin fetches these read endpoints and candidate decisions
over plain JSON. Writes stay on the model + explicit-request path, so the
panel deliberately exposes no create/revise/archive endpoints.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Response, status

from .operations import BridgeError, MemoryOperations

_BRIDGE_STATUS = {
    "resource_not_found": status.HTTP_404_NOT_FOUND,
    "revision_conflict": status.HTTP_409_CONFLICT,
    "memory_access_denied": status.HTTP_403_FORBIDDEN,
    "invalid_request": status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def create_app(operations: MemoryOperations) -> FastAPI:
    app = FastAPI(title="Butler Memory Bridge", version="0.1.0")

    def _bridge_error(error: BridgeError) -> HTTPException:
        return HTTPException(
            status_code=_BRIDGE_STATUS.get(error.code, status.HTTP_400_BAD_REQUEST),
            detail={"code": error.code, "message": error.message},
        )

    @app.get("/health/live")
    async def health_live() -> dict[str, str]:
        return {"status": "live"}

    @app.get("/v1/memories")
    async def list_memories(
        include_archived: bool = False,
        kind: str | None = None,
        limit: int = Query(default=50, ge=1, le=100),
    ) -> dict[str, Any]:
        try:
            return await operations.list_memories(
                include_archived=include_archived, kind=kind, limit=limit
            )
        except BridgeError as exc:
            raise _bridge_error(exc) from exc

    @app.get("/v1/memories/search")
    async def search_memories(
        query: str | None = None,
        kind: str | None = None,
        limit: int = Query(default=10, ge=1, le=20),
    ) -> dict[str, Any]:
        try:
            return await operations.search_memories(query=query, kind=kind, limit=limit)
        except BridgeError as exc:
            raise _bridge_error(exc) from exc

    @app.get("/v1/memories/{memory_id}/revisions")
    async def memory_revisions(memory_id: UUID) -> dict[str, Any]:
        try:
            return await operations.list_revisions(memory_id=memory_id)
        except BridgeError as exc:
            raise _bridge_error(exc) from exc

    @app.get("/v1/memory-candidates")
    async def memory_candidates(
        status_filter: str | None = Query(default=None, alias="status"),
        limit: int = Query(default=50, ge=1, le=100),
    ) -> dict[str, Any]:
        try:
            return await operations.list_candidates(
                status=status_filter, limit=limit
            )
        except BridgeError as exc:
            raise _bridge_error(exc) from exc

    @app.post("/v1/memory-candidates/{candidate_id}/accept")
    async def accept_candidate(candidate_id: UUID) -> dict[str, Any]:
        try:
            return await operations.accept_candidate(candidate_id=candidate_id)
        except BridgeError as exc:
            raise _bridge_error(exc) from exc

    @app.post("/v1/memory-candidates/{candidate_id}/reject")
    async def reject_candidate(candidate_id: UUID) -> dict[str, Any]:
        try:
            return await operations.reject_candidate(candidate_id=candidate_id)
        except BridgeError as exc:
            raise _bridge_error(exc) from exc

    return app
