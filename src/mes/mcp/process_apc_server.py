# -*- coding: utf-8 -*-
"""MCP server for read-only APC process tools."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from src.mes.process_tools.service import ProcessToolService


SERVICE = ProcessToolService()


def get_process_tool_catalog() -> Dict[str, Any]:
    """Return read-only process tools available through this MCP server."""
    return SERVICE.catalog()


def predict_process_a_apc(
    task_rows: List[Dict[str, Any]],
    machine_state: Dict[str, Any],
    recipe: Optional[List[float]] = None,
    queue_info: Optional[Dict[str, Any]] = None,
    current_time: int = 0,
) -> Dict[str, Any]:
    """Predict Process A APC quality for a proposed setting.

    This tool is read-only. It does not apply recipes, dispatch lots, or mutate
    MES/equipment state.
    """
    arguments: Dict[str, Any] = {
        "task_rows": task_rows,
        "machine_state": machine_state,
        "queue_info": queue_info or {},
        "current_time": current_time,
    }
    if recipe is not None:
        arguments["recipe"] = recipe
    return SERVICE.run_tool("predict_process_a_apc", arguments)


def build_mcp_server() -> FastMCP:
    server = FastMCP(
        "Manufacturing AI Process Tools",
        instructions=(
            "Read-only manufacturing process tools. Use these tools to run APC "
            "predictions and explain numeric outputs. Do not infer that any "
            "recipe or equipment command was executed."
        ),
    )
    server.tool(
        name="get_process_tool_catalog",
        description="List available read-only process model tools and schemas.",
    )(get_process_tool_catalog)
    server.tool(
        name="predict_process_a_apc",
        description=(
            "Predict Process A QA for task_rows, machine_state, and optional "
            "recipe. Returns recipe, predicted_qa, target_spec, quality_risk, "
            "and explanation factors. Read-only."
        ),
    )(predict_process_a_apc)
    return server


def main() -> None:
    build_mcp_server().run(transport="stdio")


if __name__ == "__main__":
    main()
