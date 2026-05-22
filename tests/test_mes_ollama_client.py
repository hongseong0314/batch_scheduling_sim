import json

import httpx

from src.mes.agent_runtime.ollama_client import OllamaChatClient


def test_ollama_client_sends_tools_to_chat_endpoint() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "predict_process_a_apc",
                                "arguments": {"machine_state": {"u": 1}},
                            }
                        }
                    ],
                }
            },
        )

    client = OllamaChatClient(
        model="gemma4:latest",
        api_base="http://ollama.local:11434",
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

    assert captured["url"] == "http://ollama.local:11434/api/chat"
    assert captured["payload"]["model"] == "gemma4:latest"
    assert captured["payload"]["stream"] is False
    assert captured["payload"]["tools"][0]["function"]["name"] == "predict_process_a_apc"
    assert response["message"]["tool_calls"][0]["function"]["name"] == "predict_process_a_apc"


def test_ollama_client_maps_continue_completion_and_request_options() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "ok"}})

    client = OllamaChatClient(
        model="qwen3:latest",
        api_base="http://ollama.local:11434",
        default_completion_options={
            "contextLength": 32768,
            "maxTokens": 6144,
            "temperature": 1.0,
            "topP": 0.95,
            "topK": 20,
            "stop": ["</s>"],
            "reasoning": True,
            "keepAlive": "30m",
        },
        request_options={
            "headers": {"X-MES-Agent": "process-chat"},
            "extraBodyProperties": {"format": "json"},
        },
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    client.chat(messages=[{"role": "user", "content": "predict"}], tools=[])

    assert captured["headers"]["x-mes-agent"] == "process-chat"
    assert captured["payload"]["options"] == {
        "num_ctx": 32768,
        "num_predict": 6144,
        "temperature": 1.0,
        "top_p": 0.95,
        "top_k": 20,
        "stop": ["</s>"],
    }
    assert captured["payload"]["think"] is True
    assert captured["payload"]["keep_alive"] == "30m"
    assert captured["payload"]["format"] == "json"
