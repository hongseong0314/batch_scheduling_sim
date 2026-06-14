from tests.mes_api_support import client
from src.mes.agent_runtime import process_chat as process_chat_module
from src.mes.agent_runtime.process_chat import DEFAULT_AGENT_CONFIG, ProcessChatService


def test_process_chat_answers_a_apc_question_without_external_llm() -> None:
    response = client.post(
        "/api/v2/process-chat",
        json={
            "message": (
                "A 공정에서 spec_a 48~53이고 u=6, m_age=12, "
                "recipe=[10,2,1]이면 QA가 어떻게 나올까?"
            ),
            "use_llm": False,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "local_process_tool"
    assert body["agent_run_id"].startswith("ARUN_")
    assert "predicted_qa" in body["answer"]
    assert body["tool_calls"][0]["tool_name"] == "predict_process_a_apc"
    assert body["tool_calls"][0]["result"]["stage"] == "A"


def test_process_chat_rejects_empty_message() -> None:
    response = client.post("/api/v2/process-chat", json={"message": ""})

    assert response.status_code == 400
    assert response.json()["detail"] == "EMPTY_CHAT_MESSAGE"


def test_process_chat_models_lists_continue_style_models() -> None:
    response = client.get("/api/v2/process-chat/models")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    assert {"name", "provider", "model", "roles", "capabilities"} <= set(body["items"][0])


def test_process_chat_default_config_path_is_runtime_config() -> None:
    assert str(DEFAULT_AGENT_CONFIG) == "config/mes-process-agent.yaml"


def test_process_chat_model_catalog_supports_env_config_override(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "custom-agent.yaml"
    config_path.write_text(
        """
name: Custom
version: 1.0.0
schema: v1
models:
  - name: Custom OpenAI
    provider: openai
    model: gpt-test
    roles:
      - chat
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("MES_PROCESS_AGENT_CONFIG", str(config_path))

    catalog = ProcessChatService().model_catalog()

    assert catalog["items"][0]["name"] == "Custom OpenAI"
    assert catalog["items"][0]["provider"] == "openai"


def test_process_chat_model_catalog_exposes_chat_models_only(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "custom-agent.yaml"
    config_path.write_text(
        """
name: Custom
version: 1.0.0
schema: v1
models:
  - name: Chat Model
    provider: ollama
    model: qwen3:latest
    roles:
      - chat
  - name: Autocomplete Model
    provider: ollama
    model: qwen2.5-coder:1.5b-base
    roles:
      - autocomplete
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("MES_PROCESS_AGENT_CONFIG", str(config_path))

    catalog = ProcessChatService().model_catalog()

    assert [item["name"] for item in catalog["items"]] == ["Chat Model"]


class FakeRuntime:
    def __init__(self) -> None:
        self.calls = []

    def run(self, message, mode="agent", max_steps=5):
        self.calls.append({"message": message, "mode": mode, "max_steps": max_steps})
        return {
            "model": "fake-model",
            "mode": mode,
            "status": "completed",
            "answer": "agent answer",
            "tool_calls": [{"tool_name": "get_fab_snapshot", "status": "executed"}],
            "agent_trace": [{"type": "llm_response"}, {"type": "tool_call"}],
            "visual_artifacts": [
                {
                    "artifact_id": "VIZ_CHAT",
                    "artifact_type": "equipment_timeseries",
                }
            ],
        }


def test_process_chat_passes_agent_mode_and_max_steps_to_runtime(monkeypatch) -> None:
    fake_runtime = FakeRuntime()

    def fake_build_runtime(*args, **kwargs):
        return fake_runtime

    monkeypatch.setattr(process_chat_module, "build_runtime_from_config", fake_build_runtime)

    result = ProcessChatService().ask(
        {
            "message": "현재 fab 상태 알려줘",
            "mode": "agent",
            "max_steps": 7,
            "use_llm": True,
        }
    )

    assert fake_runtime.calls == [
        {"message": "현재 fab 상태 알려줘", "mode": "agent", "max_steps": 7}
    ]
    assert result["mode"] == "llm_agent"
    assert result["status"] == "completed"
    assert result["agent_run_id"].startswith("ARUN_")
    assert result["agent_trace"][1]["type"] == "tool_call"
    assert result["visual_artifacts"][0]["artifact_id"] == "VIZ_CHAT"
    stored = ProcessChatService().agent_runs.get_run(result["agent_run_id"])
    assert stored["found"] is False


def test_process_chat_service_stores_agent_run_for_llm_request(monkeypatch) -> None:
    fake_runtime = FakeRuntime()

    def fake_build_runtime(*args, **kwargs):
        return fake_runtime

    monkeypatch.setattr(process_chat_module, "build_runtime_from_config", fake_build_runtime)
    service = ProcessChatService()

    result = service.ask(
        {
            "message": "현재 fab 상태 알려줘",
            "mode": "agent",
            "max_steps": 4,
            "use_llm": True,
        }
    )
    stored = service.agent_runs.get_run(result["agent_run_id"])

    assert stored["found"] is True
    assert stored["question"] == "현재 fab 상태 알려줘"
    assert stored["status"] == "completed"
    assert stored["metadata"]["max_steps"] == 4
    assert stored["tool_calls"][0]["tool_name"] == "get_fab_snapshot"


def test_agent_runs_api_lists_and_returns_chat_runs() -> None:
    response = client.post(
        "/api/v2/process-chat",
        json={
            "message": (
                "A 공정에서 spec_a 48~53이고 u=6, m_age=12, "
                "recipe=[10,2,1]이면 QA가 어떻게 나올까?"
            ),
            "use_llm": False,
        },
    )
    agent_run_id = response.json()["agent_run_id"]

    listing = client.get("/api/v2/agent-runs")
    detail = client.get(f"/api/v2/agent-runs/{agent_run_id}")

    assert listing.status_code == 200
    assert any(item["agent_run_id"] == agent_run_id for item in listing.json()["items"])
    assert detail.status_code == 200
    assert detail.json()["agent_run_id"] == agent_run_id
    assert detail.json()["tool_calls"][0]["tool_name"] == "predict_process_a_apc"


def test_control_room_mounts_chat_page_and_nav() -> None:
    html = client.get("/mes").text

    assert 'href="#chat"' in html
    assert 'id="nav-chat"' in html
    assert 'id="chat-page"' in html
    assert 'id="chat-form"' in html
    assert 'id="chat-model"' in html
    assert 'id="chat-mode"' in html
    assert 'id="chat-max-steps"' in html
    assert 'id="chat-active-inspector"' in html
    assert 'id="chat-inspector-chart"' in html
    assert 'id="chat-inspector-data"' in html
    assert 'id="chat-inspector-events"' in html
    assert 'id="chat-inspector-divider"' in html
    assert 'id="ai-dev-agent-run-body"' in html
    assert 'id="ai-dev-agent-run-detail"' in html
    assert "/api/v2/process-chat/models" in html
    assert "/api/v2/process-chat" in html
    assert "/api/v2/agent-runs" in html
    assert html.count('class="button compact chat-example"') == 7
    assert (
        'data-message="A 공정에서 spec_a 48~53이고 u=6, m_age=12, '
        'recipe=[10,2,1]이면 QA가 어떻게 나올까?">A recipe QA</button>'
    ) in html
    assert (
        'data-message="현재 fab 상태와 active policy stack을 분석해서 공정별 WIP, '
        '가동 상태, 병목과 근거를 설명해줘">Fab analysis</button>'
    ) in html


def test_control_room_chat_script_supports_visual_artifacts_and_inspector_actions() -> None:
    html = client.get("/mes").text

    assert "visual_artifacts: payload.visual_artifacts || []" in html
    assert "activateChatArtifact" in html
    assert "renderChatInspector" in html
    assert "chat-inspector-open" in html
    assert "chat-inspector-fullscreen" in html
    assert "process_a_spatial_quality" in html
    assert "spatial_quality_map" in html
    assert "renderSpatialQualityMap" in html
    assert "SIMULATED_SPATIAL_QUALITY" in html
