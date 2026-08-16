"""Offline tests for the stdio MCP server surface.

No database and no network: handlers are fakes, so this suite proves the
JSON-RPC/MCP protocol behavior only. Domain behavior is already covered by
the parent ai-butler-framework suite.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from ai_butler_memory_mcp.mcp_server import McpTool, StdioMcpServer


async def _echo(arguments):
    return {"echoed": dict(arguments)}


def _server() -> StdioMcpServer:
    return StdioMcpServer(
        server_name="test-memory",
        server_version="0.0.1",
        tools=[
            McpTool(
                name="memory_list",
                description="list memories",
                input_schema={
                    "type": "object",
                    "properties": {"limit": {"type": "integer"}},
                },
                handler=_echo,
            )
        ],
        instructions="test instructions",
    )


def _answer(server: StdioMcpServer, payload: dict):
    return asyncio.run(server.handle(payload))


def test_initialize_negotiates_protocol_version():
    server = _server()
    response = _answer(
        server,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "dsh", "version": "0.1.0"},
            },
        },
    )
    assert response["result"]["protocolVersion"] == "2025-06-18"
    assert response["result"]["serverInfo"]["name"] == "test-memory"
    assert response["result"]["capabilities"]["tools"]["listChanged"] is False
    assert "instructions" in response["result"]


def test_initialize_rejects_unknown_version():
    server = _server()
    response = _answer(
        server,
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "initialize",
            "params": {"protocolVersion": "1999-01-01", "clientInfo": {}},
        },
    )
    assert response["error"]["code"] == -32602


def test_notifications_answer_nothing():
    server = _server()
    response = _answer(
        server,
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert response is None


def test_ping_answers():
    server = _server()
    response = _answer(server, {"jsonrpc": "2.0", "id": 3, "method": "ping"})
    assert response["result"] == {}


def test_tools_list_exposes_definitions():
    server = _server()
    response = _answer(server, {"jsonrpc": "2.0", "id": 4, "method": "tools/list"})
    tools = response["result"]["tools"]
    assert [tool["name"] for tool in tools] == ["memory_list"]
    assert tools[0]["inputSchema"]["type"] == "object"


def test_tools_call_returns_text_content():
    server = _server()
    response = _answer(
        server,
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "memory_list", "arguments": {"limit": 5}},
        },
    )
    content = response["result"]["content"]
    assert content[0]["type"] == "text"
    assert json.loads(content[0]["text"]) == {"echoed": {"limit": 5}}
    assert "isError" not in response["result"]


def test_tools_call_unknown_tool_is_an_error():
    server = _server()
    response = _answer(
        server,
        {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "nope", "arguments": {}},
        },
    )
    assert response["error"]["code"] == -32602


def test_unknown_method_is_method_not_found():
    server = _server()
    response = _answer(
        server,
        {"jsonrpc": "2.0", "id": 7, "method": "resources/list"},
    )
    assert response["error"]["code"] == -32601


async def _failing(_arguments):
    raise RuntimeError("boom")


def test_handler_failure_becomes_is_error_content():
    server = StdioMcpServer(
        server_name="test-memory",
        server_version="0.0.1",
        tools=[
            McpTool(
                name="memory_broken",
                description="fails",
                input_schema={"type": "object"},
                handler=_failing,
            )
        ],
    )
    response = _answer(
        server,
        {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {"name": "memory_broken", "arguments": {}},
        },
    )
    assert response["result"]["isError"] is True
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["error"]["code"] == "internal_error"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
