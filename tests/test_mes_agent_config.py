from pathlib import Path

from src.mes.agent_runtime.config import (
    CONTINUE_DEFAULT_ROLES,
    load_agent_config,
    model_effective_capabilities,
)


def test_loads_continue_style_agent_yaml_subset(tmp_path: Path) -> None:
    config_path = tmp_path / "mes-process-agent.yaml"
    config_path.write_text(
        """
name: MES Process AI
version: 0.1.0
schema: v1
models:
  - name: Gemma4:e4 Remote
    provider: ollama
    model: gemma4:latest
    roles:
      - chat
    capabilities:
      - tool_use
    defaultCompletionOptions:
      reasoning: true
      contextLength: 128000
      maxTokens: 30000
      temperature: 0.3
mcpServers:
  - name: mes-process-tools
    type: stdio
    command: .venv/bin/python
    args:
      - -m
      - src.mes.mcp.process_apc_server
""".strip(),
        encoding="utf-8",
    )

    config = load_agent_config(config_path)

    assert config.name == "MES Process AI"
    assert config.models[0].provider == "ollama"
    assert config.models[0].model == "gemma4:latest"
    assert config.models[0].api_base == "http://localhost:11434"
    assert config.models[0].default_completion_options["reasoning"] is True
    assert config.mcp_servers[0].command == ".venv/bin/python"
    assert config.mcp_servers[0].args == ["-m", "src.mes.mcp.process_apc_server"]


def test_loads_multiple_continue_models_and_openai_fields(tmp_path: Path) -> None:
    config_path = tmp_path / "multi-agent.yaml"
    config_path.write_text(
        """
name: Local Config
version: 1.0.0
schema: v1
models:
  - name: Gemma4:e4 Remote
    provider: ollama
    model: gemma4:latest
    roles:
      - chat
      - edit
    capabilities:
      - tool_use
    defaultCompletionOptions:
      contextLength: 128000
      maxTokens: 30000
      temperature: 1.0
  - name: OpenAI GPT
    provider: openai
    model: gpt-4.1-mini
    apiBase: https://api.openai.com/v1
    apiKey: $OPENAI_API_KEY
    roles:
      - chat
    capabilities:
      - tool_use
    defaultCompletionOptions:
      maxTokens: 4096
      temperature: 0.2
""".strip(),
        encoding="utf-8",
    )

    config = load_agent_config(config_path)

    assert [model.name for model in config.models] == ["Gemma4:e4 Remote", "OpenAI GPT"]
    assert config.models[0].provider == "ollama"
    assert config.models[0].default_completion_options["contextLength"] == 128000
    assert config.models[1].provider == "openai"
    assert config.models[1].api_base == "https://api.openai.com/v1"
    assert config.models[1].api_key == "$OPENAI_API_KEY"


def test_loads_continue_nested_model_and_mcp_options(tmp_path: Path) -> None:
    config_path = tmp_path / "continue.yaml"
    config_path.write_text(
        r"""
name: Local Config
version: 1.0.0
schema: v1
models:
  - name: OpenAI Compatible
    provider: openai
    model: gpt-4o
    apiBase: https://openai-compatible.local/v1
    apiKey: ${{ secrets.OPENAI_API_KEY }}
    capabilities: []
    defaultCompletionOptions:
      contextLength: 128000
      maxTokens: 4096
      temperature: 0.2
      topP: 0.95
      stop:
        - "\n"
      reasoning: true
      reasoningBudgetTokens: 1024
    requestOptions:
      timeout: 30
      verifySsl: false
      headers:
        X-MES-Agent: process-chat
      extraBodyProperties:
        seed: 7
  - name: Qwen Autocomplete
    provider: ollama
    model: qwen2.5-coder:1.5b-base
    roles:
      - autocomplete
    autocompleteOptions:
      debounceDelay: 250
      maxPromptTokens: 1024
mcpServers:
  - name: mes-process-tools
    type: stdio
    command: .venv/bin/python
    args:
      - -m
      - src.mes.mcp.process_apc_server
    cwd: .
    env:
      MES_MODE: test
    connectionTimeout: 15
rules:
  - Give concise answers
prompts:
  - name: explain
    description: Explain process result
    prompt: |
      Explain the APC result.
context:
  - provider: file
docs:
  - name: Continue
    startUrl: https://docs.continue.dev
data:
  - name: Local Data
    destination: file:///tmp/continue-data
    schema: 0.2.0
""".strip(),
        encoding="utf-8",
    )

    config = load_agent_config(config_path)

    assert config.models[0].roles == CONTINUE_DEFAULT_ROLES
    assert config.models[0].request_options["timeout"] == 30
    assert config.models[0].request_options["verifySsl"] is False
    assert config.models[0].request_options["headers"]["X-MES-Agent"] == "process-chat"
    assert config.models[0].request_options["extraBodyProperties"]["seed"] == 7
    assert "tool_use" in model_effective_capabilities(config.models[0])
    assert config.models[1].autocomplete_options["debounceDelay"] == 250
    assert config.mcp_servers[0].cwd == "."
    assert config.mcp_servers[0].env == {"MES_MODE": "test"}
    assert config.mcp_servers[0].connection_timeout == 15


def test_loads_continue_yaml_anchors_and_merge_keys(tmp_path: Path) -> None:
    config_path = tmp_path / "anchors.yaml"
    config_path.write_text(
        """
%YAML 1.1
---
name: Anchored Config
version: 1.0.0
schema: v1
model_defaults: &model_defaults
  provider: openai
  apiKey: my-api-key
  apiBase: https://api.example.com/llm
models:
  - name: mistral
    <<: *model_defaults
    model: mistral-7b-instruct
    roles:
      - chat
      - edit
  - name: qwen2.5-coder-7b-base
    <<: *model_defaults
    model: qwen2.5-coder-7b-base
    roles:
      - autocomplete
""".strip(),
        encoding="utf-8",
    )

    config = load_agent_config(config_path)

    assert config.models[0].provider == "openai"
    assert config.models[0].api_key == "my-api-key"
    assert config.models[0].api_base == "https://api.example.com/llm"
    assert config.models[1].provider == "openai"
    assert config.models[1].roles == ["autocomplete"]


def test_skips_continue_hub_model_references_without_local_provider(tmp_path: Path) -> None:
    config_path = tmp_path / "hub.yaml"
    config_path.write_text(
        """
name: Hub Mixed Config
version: 1.0.0
schema: v1
models:
  - uses: anthropic/claude-3.5-sonnet
    with:
      ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    override:
      defaultCompletionOptions:
        temperature: 0.8
  - name: Local OpenAI
    provider: openai
    model: gpt-4o
""".strip(),
        encoding="utf-8",
    )

    config = load_agent_config(config_path)

    assert [model.name for model in config.models] == ["Local OpenAI"]
