from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hindsight_api.engine.llm_wrapper import LLMProvider, requires_api_key
from hindsight_api.engine.providers.responses_api_llm import ResponsesAPILLM

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "Recall semantic memories",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    }
]


@pytest.mark.parametrize(
    "base_url,expected",
    [
        ("https://api.openai.com/v1", "https://api.openai.com/v1/responses"),
        ("https://api.openai.com/v1/", "https://api.openai.com/v1/responses"),
        ("https://api.openai.com/v1/responses", "https://api.openai.com/v1/responses"),
        ("http://127.0.0.1:2455/backend-api/custom", "http://127.0.0.1:2455/backend-api/custom/responses"),
    ],
)
def test_responses_api_normalizes_endpoint(base_url: str, expected: str):
    llm = ResponsesAPILLM(
        provider="responses-api",
        api_key="test-key",
        base_url=base_url,
        model="gpt-4o-mini",
    )
    assert llm._responses_url() == expected


def test_responses_api_requires_api_key():
    assert requires_api_key("responses-api") is True


def test_llm_provider_uses_responses_api_impl():
    llm = LLMProvider(
        provider="responses-api",
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-4o-mini",
    )
    assert isinstance(llm._provider_impl, ResponsesAPILLM)


@pytest.mark.asyncio
async def test_responses_api_call_uses_bearer_auth_and_normalized_url():
    llm = ResponsesAPILLM(
        provider="responses-api",
        api_key="test-key",
        base_url="https://api.openai.com/v1/",
        model="gpt-4o-mini",
    )
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None

    with patch.object(llm._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = response
        with patch.object(llm, "_parse_sse_stream", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = "ok"
            await llm.call(messages=[{"role": "user", "content": "hello"}], max_retries=0)

    sent_url = mock_post.call_args.args[0]
    sent_headers = mock_post.call_args.kwargs["headers"]
    sent_payload = mock_post.call_args.kwargs["json"]

    assert sent_url == "https://api.openai.com/v1/responses"
    assert sent_headers["Authorization"] == "Bearer test-key"
    assert sent_payload["input"] == [{"role": "user", "content": "hello"}]
    assert sent_payload["store"] is False
    assert sent_payload["stream"] is True


@pytest.mark.asyncio
async def test_responses_api_call_with_tools_translates_history_and_tool_choice():
    llm = ResponsesAPILLM(
        provider="responses-api",
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        model="gpt-5-mini",
        reasoning_effort="high",
    )
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None

    messages = [
        {"role": "system", "content": "Use tools when needed."},
        {"role": "user", "content": "Recall the relevant memory."},
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "recall", "arguments": "{\"query\":\"memory\"}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "name": "recall", "content": "{\"ok\":true}"},
    ]

    with patch.object(llm._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = response
        with patch.object(llm, "_parse_sse_tool_stream", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = (None, [])
            await llm.call_with_tools(
                messages=messages,
                tools=TOOLS,
                tool_choice={"type": "function", "function": {"name": "recall"}},
                max_retries=0,
            )

    sent_payload = mock_post.call_args.kwargs["json"]

    assert sent_payload["instructions"] == "Use tools when needed."
    assert sent_payload["tool_choice"] == {"type": "function", "name": "recall"}
    assert sent_payload["reasoning"] == {"effort": "high"}
    assert sent_payload["input"] == [
        {"role": "user", "content": "Recall the relevant memory."},
        {"type": "function_call", "call_id": "call-1", "name": "recall", "arguments": "{\"query\":\"memory\"}"},
        {"type": "function_call_output", "call_id": "call-1", "output": "{\"ok\":true}"},
    ]
