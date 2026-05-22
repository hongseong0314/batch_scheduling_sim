import json

import httpx

from src.mes.agent_runtime.openai_client import OpenAIChatClient


def test_openai_client_sends_tools_to_chat_completions_endpoint() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "predict_process_a_apc",
                                        "arguments": "{\"machine_state\":{\"u\":1}}",
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        )

    client = OpenAIChatClient(
        model="gpt-4.1-mini",
        api_base="https://openai-compatible.local/v1",
        api_key="sk-test",
        default_completion_options={"maxTokens": 4096, "temperature": 0.2, "topP": 0.95},
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    response = client.chat(
        messages=[{"role": "user", "content": "predict"}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "predict_process_a_apc",
                    "parameters": {"type": "object"},
                },
            }
        ],
    )

    assert captured["url"] == "https://openai-compatible.local/v1/chat/completions"
    assert captured["auth"] == "Bearer sk-test"
    assert captured["payload"]["model"] == "gpt-4.1-mini"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["max_tokens"] == 4096
    assert captured["payload"]["tools"][0]["function"]["name"] == "predict_process_a_apc"
    assert response["message"]["tool_calls"][0]["function"]["name"] == "predict_process_a_apc"


def test_openai_client_maps_continue_request_options_and_ignores_ollama_only_options() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
        )

    client = OpenAIChatClient(
        model="gpt-4o",
        api_base="https://openai-compatible.local/v1",
        api_key="sk-test",
        default_completion_options={
            "maxTokens": 4096,
            "temperature": 0.2,
            "topP": 0.95,
            "topK": 20,
            "contextLength": 128000,
            "reasoning": True,
            "stop": ["</s>"],
        },
        request_options={
            "headers": {"X-MES-Agent": "process-chat"},
            "extraBodyProperties": {"seed": 7},
        },
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    client.chat(messages=[{"role": "user", "content": "predict"}], tools=[])

    assert captured["headers"]["authorization"] == "Bearer sk-test"
    assert captured["headers"]["x-mes-agent"] == "process-chat"
    assert captured["payload"]["max_tokens"] == 4096
    assert captured["payload"]["temperature"] == 0.2
    assert captured["payload"]["top_p"] == 0.95
    assert captured["payload"]["stop"] == ["</s>"]
    assert captured["payload"]["seed"] == 7
    assert "topK" not in captured["payload"]
    assert "contextLength" not in captured["payload"]
    assert "reasoning" not in captured["payload"]
