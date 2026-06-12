from src.mes.agent_runtime.mes_tools import MESAgentToolService
from src.mes.runtime.context import MESAPIContext
from src.objects import Task


def test_mes_agent_tool_catalog_exposes_read_only_runtime_tools() -> None:
    service = MESAgentToolService(MESAPIContext())

    catalog = service.catalog()
    by_name = {tool["name"]: tool for tool in catalog["tools"]}

    assert "predict_process_a_apc" in by_name
    assert "get_fab_snapshot" in by_name
    assert "get_policy_stack" in by_name
    assert "get_candidate_portfolio_latest" in by_name
    assert "get_assignment_trace" in by_name
    assert "list_equipment_metrics" in by_name
    assert "query_equipment_timeseries" in by_name
    assert "query_equipment_anomalies" in by_name
    assert "generate_process_a_l1_candidates" in by_name
    assert "generate_process_b_l1_candidates" in by_name
    assert "generate_process_c_l1_candidates" in by_name
    assert "annotate_process_a_l2_apc" in by_name
    assert "annotate_process_b_l2_apc" in by_name
    assert "annotate_process_c_l2_pack_quality" in by_name
    assert by_name["generate_process_c_l1_candidates"]["layer"] == "L1"
    assert by_name["annotate_process_c_l2_pack_quality"]["layer"] == "L2"
    assert all(tool["read_only"] is True for tool in catalog["tools"])


def test_mes_agent_visual_tools_return_typed_equipment_artifacts() -> None:
    context = MESAPIContext()
    context.env.time = 20
    context.env.env_A.event_log = [
        {
            "timestamp": 10,
            "event_type": "task_completed",
            "machine_id": "A_0",
            "task_uids": [1, 2],
            "quality_values": [49.0, 51.0],
            "avg_quality": 50.0,
            "target_specs": [
                {"low": 48.0, "high": 53.0},
                {"low": 48.0, "high": 53.0},
            ],
        },
        {
            "timestamp": 14,
            "event_type": "equipment_alarm",
            "machine_id": "A_0",
            "alarm_code": "TEMP_HIGH",
            "severity": "critical",
        },
    ]
    service = MESAgentToolService(context)

    catalog = service.run_tool(
        "list_equipment_metrics",
        {"equipment_ids": ["LITHO-01"]},
    )
    timeseries = service.run_tool(
        "query_equipment_timeseries",
        {
            "equipment_ids": ["LITHO-01"],
            "metrics": ["quality", "throughput"],
            "time_range": {"type": "relative", "value": 15, "unit": "day"},
            "aggregation": "daily",
        },
    )
    anomalies = service.run_tool(
        "query_equipment_anomalies",
        {
            "equipment_ids": ["A_0"],
            "time_range": {"type": "relative", "value": 15, "unit": "day"},
            "severity": ["warning", "critical"],
        },
    )

    assert catalog["metrics"] == [
        "quality",
        "utilization",
        "throughput",
        "alarm",
        "anomaly",
    ]
    assert timeseries["visual_artifacts"][0]["artifact_type"] == "equipment_timeseries"
    assert timeseries["visual_artifacts"][0]["provenance"]["time_basis"] == "SIMULATION_STEP"
    assert anomalies["visual_artifacts"][0]["artifact_type"] == "equipment_anomalies"
    assert anomalies["observed_alarm_count"] == 1


def test_mes_agent_tool_service_returns_compact_fab_snapshot() -> None:
    service = MESAgentToolService(MESAPIContext())

    result = service.run_tool("get_fab_snapshot", {})

    assert {"run_id", "time", "kpis", "stages", "active_correlation_id"} <= set(result)
    assert {"A", "B", "C"} <= set(result["stages"])
    assert {"wait", "running", "idle", "total_wip"} <= set(result["stages"]["A"])


def test_mes_agent_tool_service_delegates_process_a_apc_prediction() -> None:
    service = MESAgentToolService(MESAPIContext())

    result = service.run_tool(
        "predict_process_a_apc",
        {
            "task_rows": [{"task_uid": "T0", "spec_a": [48.0, 53.0]}],
            "machine_state": {"u": 6, "m_age": 12},
            "recipe": [10.0, 2.0, 1.0],
        },
    )

    assert result["stage"] == "A"
    assert result["predicted_qa"]
    assert result["quality_risk"] in {"LOW", "MEDIUM", "HIGH"}


def test_mes_agent_l1_tools_return_abc_candidate_surfaces() -> None:
    context = MESAPIContext()
    service = MESAgentToolService(context)

    a_result = service.run_tool("generate_process_a_l1_candidates", {"max_candidates": 2})
    assert a_result["layer"] == "L1"
    assert a_result["operation_id"] == "A"
    assert a_result["candidate_count"] >= 1
    assert a_result["candidates"][0]["equipment_id"].startswith("A_")

    context.env.reset(seed_initial_tasks=False)
    context.env.env_B.add_tasks(
        [
            Task(uid=101, job_id="JOB_B", due_date=50, spec_a=(48.0, 53.0)),
            Task(uid=102, job_id="JOB_B", due_date=50, spec_a=(48.0, 53.0)),
        ]
    )
    b_result = service.run_tool("generate_process_b_l1_candidates", {"max_candidates": 3})
    assert b_result["operation_id"] == "B"
    assert b_result["candidate_count"] == 1
    assert b_result["candidates"][0]["equipment_id"].startswith("B_")

    context.env.reset(seed_initial_tasks=False)
    c_tasks = []
    for uid in range(201, 205):
        task = Task(uid=uid, job_id="JOB_C", due_date=60, spec_a=(48.0, 53.0))
        task.customer_id = "ALPHA"
        task.material_type = "plastic"
        task.color = "red"
        task.realized_qa_B = 50.0
        c_tasks.append(task)
    context.env.env_C.add_tasks(c_tasks, current_time=0)
    c_result = service.run_tool("generate_process_c_l1_candidates", {"max_candidates": 3})
    assert c_result["operation_id"] == "C"
    assert c_result["candidate_count"] >= 1
    assert c_result["candidates"][0]["features"]["compatibility"] >= 0.9


def test_mes_agent_l2_tools_annotate_abc_candidates() -> None:
    context = MESAPIContext()
    service = MESAgentToolService(context)

    a_result = service.run_tool("annotate_process_a_l2_apc", {"max_candidates": 1})
    assert a_result["layer"] == "L2"
    assert a_result["operation_id"] == "A"
    assert a_result["annotations"][0]["l2_annotation"]["recipe_id"]
    assert a_result["annotations"][0]["quality_risk"] in {"LOW", "MEDIUM", "HIGH"}

    context.env.reset(seed_initial_tasks=False)
    context.env.env_B.add_tasks(
        [
            Task(uid=301, job_id="JOB_B", due_date=50, spec_a=(48.0, 53.0)),
            Task(uid=302, job_id="JOB_B", due_date=50, spec_a=(48.0, 53.0)),
        ]
    )
    b_result = service.run_tool("annotate_process_b_l2_apc", {"max_candidates": 1})
    assert b_result["operation_id"] == "B"
    assert b_result["annotations"][0]["l2_annotation"]["recipe_id"] == "SIM_B_DEFAULT"

    context.env.reset(seed_initial_tasks=False)
    c_tasks = []
    for uid in range(401, 405):
        task = Task(uid=uid, job_id="JOB_C", due_date=60, spec_a=(48.0, 53.0))
        task.customer_id = "ALPHA"
        task.material_type = "plastic"
        task.color = "blue"
        task.realized_qa_B = 50.0
        c_tasks.append(task)
    context.env.env_C.add_tasks(c_tasks, current_time=0)
    c_result = service.run_tool("annotate_process_c_l2_pack_quality", {"max_candidates": 1})
    annotation = c_result["annotations"][0]["l2_annotation"]
    assert c_result["operation_id"] == "C"
    assert annotation["compatibility"] >= 0.9
    assert annotation["quality_risk"] == "LOW"
