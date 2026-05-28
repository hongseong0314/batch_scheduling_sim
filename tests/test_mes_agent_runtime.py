from src.mes.agent_runtime.agent_loop import MESAgentRuntime
from src.mes.process_tools.service import ProcessToolService


class FakeLLMClient:
    def __init__(self) -> None:
        self.calls = []

    def chat(self, messages, tools):
        self.calls.append({"messages": messages, "tools": tools})
        if len(self.calls) == 1:
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "predict_process_a_apc",
                                "arguments": {
                                    "task_rows": [
                                        {"task_uid": "T0", "spec_a": [48.0, 53.0]}
                                    ],
                                    "machine_state": {"u": 6, "m_age": 12},
                                    "recipe": [10.0, 2.0, 1.0],
                                    "current_time": 120,
                                },
                            }
                        }
                    ],
                }
            }
        return {
            "message": {
                "role": "assistant",
                "content": "A 공정 예측 결과 predicted_qa가 계산됐고 spec 기준으로 risk가 산출됐습니다.",
            }
        }


def test_agent_runtime_executes_apc_tool_call_and_returns_final_answer() -> None:
    runtime = MESAgentRuntime(
        llm_client=FakeLLMClient(),
        tool_service=ProcessToolService(),
        model_name="gemma4:latest",
    )

    result = runtime.ask(
        "A 공정에서 spec_a 48~53, u=6, m_age=12, recipe=[10,2,1]이면 QA가 어떻게 나올까?"
    )

    assert result["answer"].startswith("A 공정 예측 결과")
    assert result["tool_calls"][0]["tool_name"] == "predict_process_a_apc"
    assert result["tool_calls"][0]["result"]["stage"] == "A"
    assert result["tool_calls"][0]["result"]["predicted_qa"]
    assert len(runtime.llm_client.calls) == 2
    assert runtime.llm_client.calls[0]["tools"][0]["function"]["name"] == "predict_process_a_apc"


def test_agent_runtime_does_not_send_tools_when_model_lacks_tool_capability() -> None:
    runtime = MESAgentRuntime(
        llm_client=FakeLLMClient(),
        tool_service=ProcessToolService(),
        model_name="chat-without-tools",
        tools_enabled=False,
    )

    result = runtime.ask("A 공정에서 spec_a 48~53이면 예측해줘")

    assert result["tool_calls"] == []
    assert runtime.llm_client.calls[0]["tools"] == []


class MultiStepLLMClient:
    def __init__(self) -> None:
        self.calls = []

    def chat(self, messages, tools):
        self.calls.append({"messages": messages, "tools": tools})
        if len(self.calls) == 1:
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_fab",
                            "type": "function",
                            "function": {
                                "name": "get_fab_snapshot",
                                "arguments": {},
                            },
                        }
                    ],
                }
            }
        if len(self.calls) == 2:
            return {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_apc",
                            "type": "function",
                            "function": {
                                "name": "predict_process_a_apc",
                                "arguments": {
                                    "task_rows": [
                                        {"task_uid": "T0", "spec_a": [48.0, 53.0]}
                                    ],
                                    "machine_state": {"u": 6, "m_age": 12},
                                },
                            },
                        }
                    ],
                }
            }
        return {
            "message": {
                "role": "assistant",
                "content": "fab 상태와 APC 예측을 모두 확인했습니다.",
            }
        }


class FakeAgentToolService:
    def catalog(self):
        return {
            "tools": [
                {
                    "id": "get_fab_snapshot",
                    "name": "get_fab_snapshot",
                    "description": "Return current fab state.",
                    "read_only": True,
                    "input_schema": {"type": "object", "properties": {}},
                },
                {
                    "id": "predict_process_a_apc",
                    "name": "predict_process_a_apc",
                    "description": "Predict A APC.",
                    "read_only": True,
                    "layer": "L2",
                    "operation_id": "A",
                    "policy_id": "A_RULE_BASED_APC_PREDICTOR",
                    "input_schema": {"type": "object", "properties": {}},
                },
                {
                    "id": "apply_recipe",
                    "name": "apply_recipe",
                    "description": "Unsafe recipe write.",
                    "read_only": False,
                    "input_schema": {"type": "object", "properties": {}},
                },
            ]
        }

    def openai_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
            for tool in self.catalog()["tools"]
        ]

    def run_tool(self, tool_id, arguments):
        if tool_id == "get_fab_snapshot":
            return {"time": 7, "stages": {"A": {"wait": 3}}}
        if tool_id == "predict_process_a_apc":
            return {"stage": "A", "predicted_qa": 49.7, "quality_risk": "LOW"}
        raise ValueError(f"UNSAFE_PROCESS_TOOL:{tool_id}")


def test_agent_runtime_runs_multi_step_until_final_answer() -> None:
    llm = MultiStepLLMClient()
    runtime = MESAgentRuntime(
        llm_client=llm,
        tool_service=FakeAgentToolService(),
        model_name="agent-model",
    )

    result = runtime.run("현재 fab 상태를 보고 A APC도 예측해줘", mode="agent", max_steps=5)

    assert result["mode"] == "agent"
    assert result["status"] == "completed"
    assert result["answer"] == "fab 상태와 APC 예측을 모두 확인했습니다."
    assert [call["tool_name"] for call in result["tool_calls"]] == [
        "get_fab_snapshot",
        "predict_process_a_apc",
    ]
    assert result["tool_calls"][1]["layer"] == "L2"
    assert result["tool_calls"][1]["operation_id"] == "A"
    assert result["tool_calls"][1]["policy_id"] == "A_RULE_BASED_APC_PREDICTOR"
    assert [step["type"] for step in result["agent_trace"]] == [
        "llm_response",
        "tool_call",
        "llm_response",
        "tool_call",
        "llm_response",
    ]
    assert len(llm.calls) == 3


class UnsafeToolLLMClient:
    def __init__(self) -> None:
        self.calls = []

    def chat(self, messages, tools):
        self.calls.append({"messages": messages, "tools": tools})
        return {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_write",
                        "type": "function",
                        "function": {"name": "apply_recipe", "arguments": {}},
                    }
                ],
            }
        }


def test_agent_runtime_rejects_non_read_only_tool_calls() -> None:
    runtime = MESAgentRuntime(
        llm_client=UnsafeToolLLMClient(),
        tool_service=FakeAgentToolService(),
        model_name="agent-model",
    )

    result = runtime.run("recipe를 적용해줘", mode="agent", max_steps=3)

    assert result["status"] == "policy_blocked"
    assert result["tool_calls"][0]["status"] == "rejected"
    assert result["tool_calls"][0]["policy"] == "excluded"


class SystemMessageToolLLMClient:
    def __init__(self) -> None:
        self.calls = []

    def chat(self, messages, tools):
        self.calls.append({"messages": messages, "tools": tools})
        if len(self.calls) == 1:
            return {
                "message": {
                    "role": "assistant",
                    "content": '{"tool":"get_fab_snapshot","arguments":{}}',
                }
            }
        return {"message": {"role": "assistant", "content": "system tool result 확인 완료"}}


def test_agent_runtime_supports_system_message_tool_fallback() -> None:
    llm = SystemMessageToolLLMClient()
    runtime = MESAgentRuntime(
        llm_client=llm,
        tool_service=FakeAgentToolService(),
        model_name="non-native-tool-model",
        native_tools_enabled=False,
        system_message_tools_enabled=True,
    )

    result = runtime.run("fab 상태를 확인해줘", mode="agent", max_steps=3)

    assert result["status"] == "completed"
    assert result["tool_calls"][0]["tool_name"] == "get_fab_snapshot"
    assert llm.calls[0]["tools"] == []
    assert "Available MES tools" in llm.calls[0]["messages"][0]["content"]
