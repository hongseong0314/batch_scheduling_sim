from src.mes.agent_runtime.process_chat import ProcessChatService
from src.mes.agent_runtime.sqlite_run_store import SQLiteAgentRunStore
from src.mes.sqlite_store import SQLiteMESStore


def test_sqlite_agent_run_store_reloads_completed_run(tmp_path) -> None:
    db_path = tmp_path / "mes.sqlite3"
    store = SQLiteAgentRunStore(db_path)

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
        tool_calls=[{"tool_name": "get_fab_snapshot", "status": "executed"}],
        agent_trace=[{"type": "tool_call", "tool_name": "get_fab_snapshot"}],
        visual_artifacts=[
            {
                "artifact_id": "VIZ_SQLITE",
                "artifact_type": "equipment_timeseries",
            }
        ],
        duration_ms=321,
    )

    reloaded = SQLiteAgentRunStore(db_path)
    detail = reloaded.get_run(run.agent_run_id)
    listing = reloaded.list_runs()

    assert detail["found"] is True
    assert detail["agent_run_id"] == run.agent_run_id
    assert detail["mes_run_id"] == "RUN_001"
    assert detail["status"] == "completed"
    assert detail["answer"] == "A가 병목입니다."
    assert detail["metadata"]["requested_think"] is True
    assert detail["metadata"]["model_config"]["name"] == "Gemma4 Remote"
    assert detail["tool_calls"][0]["tool_name"] == "get_fab_snapshot"
    assert detail["visual_artifacts"][0]["artifact_id"] == "VIZ_SQLITE"
    assert listing["items"][0]["agent_run_id"] == run.agent_run_id


def test_process_chat_uses_sqlite_agent_runs_when_runtime_context_has_store(tmp_path) -> None:
    db_path = tmp_path / "mes.sqlite3"

    class RuntimeContext:
        run_id = "RUN_CHAT_TEST"
        store = SQLiteMESStore(db_path)

    service = ProcessChatService(runtime_context=RuntimeContext())
    result = service.ask(
        {
            "message": (
                "A 공정에서 spec_a 48~53이고 u=6, m_age=12, "
                "recipe=[10,2,1]이면 QA가 어떻게 나올까?"
            ),
            "use_llm": False,
        }
    )

    reloaded = SQLiteAgentRunStore(db_path)
    detail = reloaded.get_run(result["agent_run_id"])

    assert detail["found"] is True
    assert detail["mes_run_id"] == "RUN_CHAT_TEST"
    assert detail["mode"] == "local_process_tool"
    assert detail["tool_calls"][0]["tool_name"] == "predict_process_a_apc"
