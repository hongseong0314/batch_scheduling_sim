# -*- coding: utf-8 -*-
"""Synchronous MCP stdio client wrapper for MES agent tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


class MCPProcessToolClient:
    """Expose a stdio MCP server behind the local agent tool-service shape."""

    def __init__(
        self,
        command: str,
        args: Optional[List[str]] = None,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.command = command
        self.args = list(args or [])
        self.cwd = cwd
        self.env = {str(key): str(value) for key, value in dict(env or {}).items()}

    def catalog(self) -> Dict[str, Any]:
        tools = anyio.run(self._list_tools)
        return {"count": len(tools), "tools": tools}

    def openai_tools(self) -> List[Dict[str, Any]]:
        items = []
        for tool in self.catalog()["tools"]:
            items.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {"type": "object"}),
                    },
                }
            )
        return items

    def run_tool(self, tool_id: str, arguments: Mapping[str, Any]) -> Dict[str, Any]:
        return anyio.run(self._call_tool, str(tool_id), dict(arguments))

    async def _list_tools(self) -> List[Dict[str, Any]]:
        async with self._session() as session:
            result = await session.list_tools()
            tools = []
            for tool in result.tools:
                tools.append(
                    {
                        "name": tool.name,
                        "id": tool.name,
                        "description": tool.description or "",
                        "input_schema": dict(tool.inputSchema or {"type": "object"}),
                        "read_only": True,
                    }
                )
            return tools

    async def _call_tool(self, tool_id: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        async with self._session() as session:
            result = await session.call_tool(tool_id, arguments)
            structured = getattr(result, "structuredContent", None)
            if isinstance(structured, Mapping):
                payload = structured.get("result", structured)
                if isinstance(payload, Mapping):
                    return dict(payload)
            for content in getattr(result, "content", []) or []:
                text = getattr(content, "text", "")
                if text:
                    parsed = json.loads(text)
                    if isinstance(parsed, Mapping):
                        return dict(parsed)
            raise ValueError(f"MCP_TOOL_RETURNED_NO_JSON:{tool_id}")

    def _server_parameters(self) -> StdioServerParameters:
        cwd = Path(self.cwd) if self.cwd else None
        env = self.env or None
        return StdioServerParameters(command=self.command, args=self.args, env=env, cwd=cwd)

    def _session(self):
        return _MCPSessionContext(self._server_parameters())


class _MCPSessionContext:
    def __init__(self, server_parameters: StdioServerParameters) -> None:
        self.server_parameters = server_parameters
        self.stdio_context = None
        self.session = None

    async def __aenter__(self) -> ClientSession:
        self.stdio_context = stdio_client(self.server_parameters)
        read, write = await self.stdio_context.__aenter__()
        self.session = ClientSession(read, write)
        session = await self.session.__aenter__()
        await session.initialize()
        return session

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.session is not None:
            await self.session.__aexit__(exc_type, exc, tb)
        if self.stdio_context is not None:
            await self.stdio_context.__aexit__(exc_type, exc, tb)
