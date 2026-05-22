# -*- coding: utf-8 -*-
"""Command line entrypoint for the local MES process agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from src.mes.agent_runtime.factory import build_runtime_from_config


DEFAULT_CONFIG = "config/mes-process-agent.yaml"


def format_cli_output(result: Dict[str, Any], json_output: bool = False) -> str:
    if json_output:
        return json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    answer = str(result.get("answer", ""))
    tool_count = len(result.get("tool_calls", []) or [])
    return f"{answer}\n\nTool calls: {tool_count}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mes-process-agent",
        description="Ask the local MES process AI agent a natural-language APC question.",
    )
    parser.add_argument("question", nargs="+", help="Natural-language process question")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help=f"Continue-style runtime config path. Default: {DEFAULT_CONFIG}",
    )
    parser.add_argument(
        "--direct-tools",
        action="store_true",
        help="Bypass MCP subprocess and call local process tools in-process.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name or model id from the Continue-style config.",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON result")
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config_path = Path(args.config)
    runtime = build_runtime_from_config(
        config_path,
        prefer_mcp=not args.direct_tools,
        cwd=str(Path.cwd()),
        model_name=args.model,
    )
    result = runtime.ask(" ".join(args.question))
    print(format_cli_output(result, json_output=bool(args.json)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
