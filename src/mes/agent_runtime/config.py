# -*- coding: utf-8 -*-
"""Continue-inspired config loading for the local MES agent runtime."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping


CONTINUE_DEFAULT_ROLES = ["chat", "edit", "apply", "summarize"]


@dataclass(frozen=True)
class ModelConfig:
    name: str
    provider: str
    model: str
    api_base: str = "http://localhost:11434"
    api_key: str = ""
    roles: List[str] = field(default_factory=lambda: ["chat"])
    capabilities: List[str] = field(default_factory=list)
    default_completion_options: Dict[str, Any] = field(default_factory=dict)
    request_options: Dict[str, Any] = field(default_factory=dict)
    max_stop_words: int | None = None
    prompt_templates: Dict[str, Any] = field(default_factory=dict)
    chat_options: Dict[str, Any] = field(default_factory=dict)
    embed_options: Dict[str, Any] = field(default_factory=dict)
    autocomplete_options: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    type: str = "stdio"
    command: str = ""
    args: List[str] = field(default_factory=list)
    url: str = ""
    env: Dict[str, str] = field(default_factory=dict)
    cwd: str = ""
    request_options: Dict[str, Any] = field(default_factory=dict)
    connection_timeout: float | None = None


@dataclass(frozen=True)
class AgentConfig:
    name: str
    version: str
    schema: str
    models: List[ModelConfig]
    mcp_servers: List[MCPServerConfig]


def load_agent_config(path: str | Path) -> AgentConfig:
    raw_path = Path(path)
    text = raw_path.read_text(encoding="utf-8")
    if raw_path.suffix.lower() == ".json" or text.lstrip().startswith("{"):
        data = json.loads(text)
    else:
        data = _parse_yaml_subset(text)
    return _agent_config_from_mapping(data)


def _agent_config_from_mapping(data: Mapping[str, Any]) -> AgentConfig:
    models = []
    for item in data.get("models", []):
        if not isinstance(item, Mapping):
            continue
        if item.get("uses") and not item.get("provider") and not item.get("model"):
            continue
        provider = str(item.get("provider", "ollama"))
        models.append(
            ModelConfig(
                name=str(item.get("name", item.get("model", provider))),
                provider=provider,
                model=str(item.get("model", "")),
                api_base=str(
                    item.get(
                        "apiBase",
                        item.get("api_base", _default_api_base(provider)),
                    )
                ),
                api_key=str(item.get("apiKey", item.get("api_key", ""))),
                roles=_string_list(item.get("roles", CONTINUE_DEFAULT_ROLES)),
                capabilities=[str(value) for value in item.get("capabilities", [])],
                default_completion_options=dict(
                    item.get("defaultCompletionOptions", item.get("default_completion_options", {}))
                ),
                request_options=dict(item.get("requestOptions", item.get("request_options", {})) or {}),
                max_stop_words=_optional_int(item.get("maxStopWords")),
                prompt_templates=dict(item.get("promptTemplates", {}) or {}),
                chat_options=dict(item.get("chatOptions", {}) or {}),
                embed_options=dict(item.get("embedOptions", {}) or {}),
                autocomplete_options=dict(item.get("autocompleteOptions", {}) or {}),
            )
        )
    return AgentConfig(
        name=str(data.get("name", "MES Process AI")),
        version=str(data.get("version", "0.1.0")),
        schema=str(data.get("schema", "v1")),
        models=models,
        mcp_servers=[
            MCPServerConfig(
                name=str(item.get("name", "")),
                type=str(item.get("type", "stdio")),
                command=str(item.get("command", "")),
                args=[str(value) for value in item.get("args", [])],
                url=str(item.get("url", "")),
                env={str(key): str(value) for key, value in dict(item.get("env", {}) or {}).items()},
                cwd=str(item.get("cwd", "")),
                request_options=dict(item.get("requestOptions", item.get("request_options", {})) or {}),
                connection_timeout=_optional_float(item.get("connectionTimeout")),
            )
            for item in data.get("mcpServers", data.get("mcp_servers", []))
            if isinstance(item, Mapping)
        ],
    )


def _default_api_base(provider: str) -> str:
    normalized = provider.lower()
    if normalized == "openai":
        return "https://api.openai.com/v1"
    return "http://localhost:11434"


def model_supports_role(model: ModelConfig, role: str) -> bool:
    return role in model.roles


def model_effective_capabilities(model: ModelConfig) -> List[str]:
    """Return Continue-style capabilities: autodetected capabilities plus config additions."""
    capabilities = set(_autodetected_capabilities(model))
    capabilities.update(str(value) for value in model.capabilities)
    return sorted(capabilities)


def _autodetected_capabilities(model: ModelConfig) -> List[str]:
    provider = model.provider.lower()
    model_id = model.model.lower()
    capabilities: set[str] = set()
    if provider == "openai":
        if any(prefix in model_id for prefix in ("gpt-", "gpt", "o1", "o3", "o4")):
            capabilities.add("tool_use")
        if any(value in model_id for value in ("gpt-4o", "gpt-4.1", "vision")):
            capabilities.add("image_input")
    if provider == "ollama":
        tool_families = ("qwen3", "qwen 3", "llama3", "llama 3", "mistral", "codestral", "devstral")
        image_families = ("qwen2.5-vl", "qwen 2.5 vl", "gemma3", "gemma 3")
        if any(value in model_id for value in tool_families):
            capabilities.add("tool_use")
        if any(value in model_id for value in image_families):
            capabilities.add("image_input")
    return sorted(capabilities)


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _parse_yaml_subset(text: str) -> Dict[str, Any]:
    """Parse the Continue YAML subset needed by the MES runtime.

    The parser is intentionally small but supports nested maps/lists, block
    scalars, comments, and the local config shapes documented by Continue.
    """
    lines = _yaml_lines(text)
    if not lines:
        return {}
    parsed, _ = _parse_block(lines, 0, lines[0][0], {})
    return dict(parsed or {})


def _yaml_lines(text: str) -> List[tuple[int, str]]:
    lines = []
    for original_line in text.splitlines():
        if original_line.strip().startswith("%YAML") or original_line.strip() == "---":
            continue
        line = _strip_comment(original_line).rstrip()
        if not line.strip():
            continue
        lines.append((len(line) - len(line.lstrip(" ")), line.strip()))
    return lines


def _parse_block(
    lines: List[tuple[int, str]],
    index: int,
    indent: int,
    anchors: Dict[str, Any],
) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    if lines[index][1].startswith("- "):
        return _parse_list(lines, index, indent, anchors)
    return _parse_mapping(lines, index, indent, anchors)


def _parse_mapping(
    lines: List[tuple[int, str]],
    index: int,
    indent: int,
    anchors: Dict[str, Any],
) -> tuple[Dict[str, Any], int]:
    data: Dict[str, Any] = {}
    while index < len(lines):
        line_indent, stripped = lines[index]
        if line_indent < indent:
            break
        if line_indent > indent:
            break
        if stripped.startswith("- "):
            break
        key, value = _split_key_value(stripped)
        anchor_name = _anchor_name(value)
        if anchor_name:
            value = None
        if key == "<<" and isinstance(value, str) and value.startswith("*"):
            _merge_anchor(data, anchors, value[1:].strip())
            index += 1
            continue
        if value in {"|", ">"}:
            block, index = _parse_block_scalar(lines, index + 1, line_indent)
            data[key] = block
            continue
        if value is None:
            if index + 1 < len(lines) and lines[index + 1][0] > line_indent:
                child, index = _parse_block(lines, index + 1, lines[index + 1][0], anchors)
                data[key] = child
                if anchor_name:
                    anchors[anchor_name] = child
            else:
                data[key] = None
                index += 1
            continue
        data[key] = _parse_scalar(value)
        if anchor_name:
            anchors[anchor_name] = data[key]
        index += 1
    return data, index


def _parse_list(
    lines: List[tuple[int, str]],
    index: int,
    indent: int,
    anchors: Dict[str, Any],
) -> tuple[List[Any], int]:
    items: List[Any] = []
    while index < len(lines):
        line_indent, stripped = lines[index]
        if line_indent < indent:
            break
        if line_indent != indent or not stripped.startswith("- "):
            break
        remainder = stripped[2:].strip()
        index += 1
        if not remainder:
            if index < len(lines) and lines[index][0] > line_indent:
                value, index = _parse_block(lines, index, lines[index][0], anchors)
            else:
                value = None
            items.append(value)
            continue
        if ":" in remainder:
            key, raw_value = _split_key_value(remainder)
            anchor_name = _anchor_name(raw_value)
            if anchor_name:
                raw_value = None
            item: Dict[str, Any] = {}
            if key == "<<" and isinstance(raw_value, str) and raw_value.startswith("*"):
                _merge_anchor(item, anchors, raw_value[1:].strip())
            elif raw_value in {"|", ">"}:
                value, index = _parse_block_scalar(lines, index, line_indent)
                item[key] = value
                if anchor_name:
                    anchors[anchor_name] = value
            elif raw_value is None:
                if index < len(lines) and lines[index][0] > line_indent:
                    value, index = _parse_block(lines, index, lines[index][0], anchors)
                    item[key] = value
                    if anchor_name:
                        anchors[anchor_name] = value
                else:
                    item[key] = None
            else:
                item[key] = _parse_scalar(raw_value)
                if anchor_name:
                    anchors[anchor_name] = item[key]
            if index < len(lines) and lines[index][0] > line_indent:
                extra, index = _parse_mapping(lines, index, lines[index][0], anchors)
                item.update(extra)
            items.append(item)
            continue
        items.append(_parse_scalar(remainder))
    return items, index


def _parse_block_scalar(
    lines: List[tuple[int, str]],
    index: int,
    parent_indent: int,
) -> tuple[str, int]:
    parts: List[str] = []
    while index < len(lines):
        line_indent, stripped = lines[index]
        if line_indent <= parent_indent:
            break
        parts.append(stripped)
        index += 1
    return "\n".join(parts), index


def _anchor_name(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    stripped = value.strip()
    if stripped.startswith("&"):
        return stripped[1:].split()[0]
    return ""


def _merge_anchor(target: Dict[str, Any], anchors: Mapping[str, Any], name: str) -> None:
    source = anchors.get(name, {})
    if not isinstance(source, Mapping):
        return
    for key, value in source.items():
        target.setdefault(str(key), value)


def _split_key_value(line: str) -> tuple[str, str | None]:
    if ":" not in line:
        return line, None
    key, value = line.split(":", 1)
    value = value.strip()
    return key.strip(), value if value else None


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            return line[:index]
    return line


def _parse_scalar(value: str | None) -> Any:
    if value is None:
        return None
    stripped = value.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
    if stripped.startswith('"') and stripped.endswith('"'):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return stripped[1:-1]
    stripped = stripped.strip("'")
    lowered = stripped.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    try:
        if "." in stripped:
            return float(stripped)
        return int(stripped)
    except ValueError:
        return stripped
