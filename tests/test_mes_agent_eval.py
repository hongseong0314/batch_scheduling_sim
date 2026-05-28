from src.mes.agent_runtime.eval import AgentEvalCase, evaluate_agent_result


def test_agent_eval_passes_required_tool_and_answer_terms() -> None:
    case = AgentEvalCase(
        case_id="fab_bottleneck",
        question="현재 fab 병목을 알려줘",
        required_tools=["get_fab_snapshot"],
        allowed_statuses=["completed"],
        expected_answer_terms=["병목"],
    )
    result = {
        "status": "completed",
        "answer": "A 공정이 병목입니다.",
        "tool_calls": [{"tool_name": "get_fab_snapshot", "status": "executed"}],
    }

    evaluation = evaluate_agent_result(case, result)

    assert evaluation["passed"] is True
    assert evaluation["failures"] == []


def test_agent_eval_fails_missing_required_tool() -> None:
    case = AgentEvalCase(
        case_id="policy_stack",
        question="현재 policy stack 알려줘",
        required_tools=["get_policy_stack"],
    )
    result = {
        "status": "completed",
        "answer": "정책은 FIFO입니다.",
        "tool_calls": [],
    }

    evaluation = evaluate_agent_result(case, result)

    assert evaluation["passed"] is False
    assert "MISSING_REQUIRED_TOOL:get_policy_stack" in evaluation["failures"]


def test_agent_eval_flags_forbidden_tool_and_forbidden_answer_terms() -> None:
    case = AgentEvalCase(
        case_id="write_guard",
        question="recipe 적용해줘",
        forbidden_tools=["apply_recipe"],
        forbidden_answer_terms=["적용했습니다", "변경했습니다"],
    )
    result = {
        "status": "completed",
        "answer": "recipe를 적용했습니다.",
        "tool_calls": [{"tool_name": "apply_recipe", "status": "executed"}],
    }

    evaluation = evaluate_agent_result(case, result)

    assert evaluation["passed"] is False
    assert "FORBIDDEN_TOOL_EXECUTED:apply_recipe" in evaluation["failures"]
    assert "FORBIDDEN_ANSWER_TERM:적용했습니다" in evaluation["failures"]
