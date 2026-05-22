import json

from src.mes.agent_runtime.cli import format_cli_output


def test_format_cli_output_supports_text_and_json() -> None:
    result = {
        "answer": "예측 QA는 49.66입니다.",
        "tool_calls": [{"tool_name": "predict_process_a_apc"}],
    }

    text = format_cli_output(result, json_output=False)
    raw_json = format_cli_output(result, json_output=True)

    assert "예측 QA는 49.66입니다." in text
    assert "Tool calls: 1" in text
    assert json.loads(raw_json)["tool_calls"][0]["tool_name"] == "predict_process_a_apc"
