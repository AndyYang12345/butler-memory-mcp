"""Dependency-free MCP (Model Context Protocol) stdio server.

Implements the JSON-RPC 2.0 subset required to serve Tools: ``initialize``,
``notifications/initialized``, ``ping``, ``tools/list`` and ``tools/call``.
stdout carries one complete JSON object per line and nothing else; all
diagnostics go to stderr. This mirrors the dependency-free MCP discipline of
the parent framework's own ``mcp_client.py``.

Protocol note: the client sends its requested ``protocolVersion`` inside
``initialize``; the server echoes it back when it is one of the supported
versions, which is what MCP negotiation expects from a server.
"""

from __future__ import annotations

import asyncio
import json
import sys
import traceback
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any

SUPPORTED_PROTOCOL_VERSIONS = (
    "2024-11-05",
    "2025-03-26",
    "2025-06-18",
    "2025-11-25",
)
_JSONRPC = "2.0"

ToolHandler = Callable[[Mapping[str, Any]], Awaitable[dict[str, Any]]]


class McpTool:
    """One model-callable capability served by this server."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        input_schema: dict[str, Any],
        handler: ToolHandler,
    ) -> None:
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self._handler = handler

    def definition(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }

    async def invoke(self, arguments: Mapping[str, Any]) -> dict[str, Any]:
        return await self._handler(arguments)


class StdioMcpServer:
    """Line-delimited JSON-RPC stdio server for the bridge tool surface."""

    def __init__(
        self,
        *,
        server_name: str,
        server_version: str,
        tools: Sequence[McpTool],
        instructions: str | None = None,
    ) -> None:
        self._name = server_name
        self._version = server_version
        self._instructions = instructions
        self._tools: dict[str, McpTool] = {tool.name: tool for tool in tools}

    def tool_names(self) -> list[str]:
        return list(self._tools)

    @staticmethod
    def _error(msg_id: Any, code: int, message: str) -> dict[str, Any]:
        return {
            "jsonrpc": _JSONRPC,
            "id": msg_id,
            "error": {"code": code, "message": message},
        }

    @staticmethod
    def _result(msg_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": _JSONRPC, "id": msg_id, "result": result}

    def _initialize(self, msg_id: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        requested = params.get("protocolVersion")
        if requested not in SUPPORTED_PROTOCOL_VERSIONS:
            return self._error(
                msg_id,
                -32602,
                f"Unsupported protocolVersion {requested!r}; "
                f"supported: {', '.join(SUPPORTED_PROTOCOL_VERSIONS)}",
            )
        result: dict[str, Any] = {
            "protocolVersion": requested,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": self._name, "version": self._version},
        }
        if self._instructions:
            result["instructions"] = self._instructions
        return self._result(msg_id, result)

    def _tools_list(self, msg_id: Any) -> dict[str, Any]:
        return self._result(
            msg_id,
            {"tools": [tool.definition() for tool in self._tools.values()]},
        )

    async def _tools_call(
        self,
        msg_id: Any,
        params: Mapping[str, Any],
    ) -> dict[str, Any]:
        name = params.get("name")
        tool = self._tools.get(name) if isinstance(name, str) else None
        if tool is None:
            return self._error(msg_id, -32602, f"Unknown tool: {name!r}")
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, Mapping):
            return self._error(msg_id, -32602, "Tool arguments must be an object")
        try:
            payload = await tool.invoke(arguments)
        except Exception as exc:  # handlers already normalize domain errors
            code = getattr(exc, "code", "internal_error")
            message = str(exc)
            return self._result(
                msg_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {"error": {"code": code, "message": message}},
                                ensure_ascii=False,
                            ),
                        }
                    ],
                    "isError": True,
                },
            )
        return self._result(
            msg_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(payload, ensure_ascii=False),
                    }
                ]
            },
        )

    async def handle(self, message: Mapping[str, Any]) -> dict[str, Any] | None:
        """Answer one parsed JSON-RPC message; notifications answer ``None``."""
        msg_id = message.get("id")
        method = message.get("method")
        if not isinstance(method, str) or not method:
            return self._error(msg_id, -32600, "Invalid Request")
        params = message.get("params")
        params = params if isinstance(params, Mapping) else {}

        if method == "initialize":
            return self._initialize(msg_id, params)
        if method.startswith("notifications/"):
            return None
        if method == "ping":
            return self._result(msg_id, {})
        if method == "tools/list":
            return self._tools_list(msg_id)
        if method == "tools/call":
            return await self._tools_call(msg_id, params)
        return self._error(msg_id, -32601, f"Method not found: {method!r}")

    @staticmethod
    def _write_frame(stdout: Any, frame: dict[str, Any]) -> None:
        stdout.write(
            json.dumps(frame, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
            + b"\n"
        )
        stdout.flush()

    async def run_forever(self) -> None:
        """Read stdin line by line until EOF, answering each message."""
        loop = asyncio.get_running_loop()
        stdin = sys.stdin.buffer
        stdout = sys.stdout.buffer
        while True:
            line = await loop.run_in_executor(None, stdin.readline)
            if not line:
                return
            text = line.decode("utf-8").strip()
            if not text:
                continue
            try:
                message = json.loads(text)
            except json.JSONDecodeError:
                frame = self._error(None, -32700, "Parse error")
                await loop.run_in_executor(None, self._write_frame, stdout, frame)
                continue
            if not isinstance(message, dict):
                frame = self._error(None, -32600, "Invalid Request")
                await loop.run_in_executor(None, self._write_frame, stdout, frame)
                continue
            try:
                response = await self.handle(message)
            except Exception:
                traceback.print_exc(file=sys.stderr)
                response = self._error(message.get("id"), -32603, "Internal error")
            if response is not None:
                await loop.run_in_executor(None, self._write_frame, stdout, response)
