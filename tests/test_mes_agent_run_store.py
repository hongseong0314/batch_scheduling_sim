from src.mes.agent_runtime.run_store import AgentRunStore


def test_agent_run_store_creates_and_completes_run() -> None:
    store = AgentRunStore()

    run = store.start_run(
        question="현재 fab 상태 알려줘",
        mode="agent",
        model_name="gemma4:latest",
        provider="ollama",
        max_steps=5,
        prompt_id="MES_AGENT_SYSTEM_PROMPT",
        prompt_version="0.1.0",
        tool_catalog_version="mes-agent-tools-v1",
        model_config={"name": "Gemma4 Remote"},
        requested_think=True,
        mes_run_id="RUN_001",
    )
    store.complete_run(
        run.agent_run_id,
        status="completed",
        answer="A가 병목입니다.",
        tool_calls=[
            {
                "tool_name": "get_fab_snapshot",
                "status": "executed",
                "policy": "allowedWithoutPermission",
            }
        ],
        agent_trace=[
            {"type": "llm_response", "step": 1, "tool_call_count": 1},
            {"type": "tool_call", "step": 1, "tool_name": "get_fab_snapshot"},
        ],
        visual_artifacts=[
            {
                "artifact_id": "VIZ_001",
                "artifact_type": "equipment_timeseries",
            }
        ],
        duration_ms=123,
    )

    detail = store.get_run(run.agent_run_id)

    assert detail["agent_run_id"] == run.agent_run_id
    assert detail["status"] == "completed"
    assert detail["answer"] == "A가 병목입니다."
    assert detail["tool_count"] == 1
    assert detail["step_count"] == 2
    assert detail["artifact_count"] == 1
    assert detail["visual_artifacts"][0]["artifact_id"] == "VIZ_001"
    assert detail["metadata"]["requested_think"] is True
    assert detail["metadata"]["model_config"]["name"] == "Gemma4 Remote"


def test_agent_run_store_lists_newest_first_and_respects_retention() -> None:
    store = AgentRunStore(max_records=2)

    first = store.start_run(
        question="first",
        mode="agent",
        model_name="m1",
        provider="ollama",
        max_steps=3,
        prompt_id="p",
        prompt_version="1",
        tool_catalog_version="tools",
        model_config={},
    )
    second = store.start_run(
        question="second",
        mode="agent",
        model_name="m1",
        provider="ollama",
        max_steps=3,
        prompt_id="p",
        prompt_version="1",
        tool_catalog_version="tools",
        model_config={},
    )
    third = store.start_run(
        question="third",
        mode="chat",
        model_name="m2",
        provider="openai",
        max_steps=1,
        prompt_id="p",
        prompt_version="1",
        tool_catalog_version="tools",
        model_config={},
    )

    items = store.list_runs()["items"]

    assert [item["agent_run_id"] for item in items] == [
        third.agent_run_id,
        second.agent_run_id,
    ]
    assert store.get_run(first.agent_run_id)["found"] is False
