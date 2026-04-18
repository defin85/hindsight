"""
Regression tests for Codex provider tool_choice normalization.

The reflect agent forces tool selection via named tool_choice dicts on early iterations:
  {"type": "function", "function": {"name": "recall"}}

The Codex Responses API expects the function name at the top level instead:
  {"type": "function", "name": "recall"}

Without normalization, Codex rejects the request with:
  400 Unknown parameter: 'tool_choice.function'
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hindsight_api.engine.providers.codex_llm import CODEX_LB_API_KEY_ENV, CodexLLM, CodexOAuthCredentials

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


def build_llm(
    *,
    api_key: str | None = "ignored",
    base_url: str = "https://chatgpt.com/backend-api",
) -> CodexLLM:
    with patch.object(
        CodexLLM,
        "_load_codex_auth",
        return_value=CodexOAuthCredentials(access_token="oauth-token", account_id="account"),
    ):
        return CodexLLM(
            provider="openai-codex",
            api_key=api_key,
            base_url=base_url,
            model="gpt-5.4-mini",
        )


@pytest.mark.asyncio
async def test_codex_normalizes_legacy_named_tool_choice_shape():
    llm = build_llm()
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    with patch.object(llm._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = response
        with patch.object(llm, "_parse_sse_tool_stream", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = (None, [])
            await llm.call_with_tools(
                messages=[{"role": "user", "content": "recall the memory"}],
                tools=TOOLS,
                tool_choice={"type": "function", "function": {"name": "recall"}},
                max_retries=0,
            )
        sent_payload = mock_post.call_args.kwargs["json"]

    assert sent_payload["tool_choice"] == {"type": "function", "name": "recall"}


@pytest.mark.asyncio
async def test_codex_forced_tool_choice_still_yields_tool_calls():
    llm = build_llm()
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    tool_call = {"id": "call-1", "name": "recall", "arguments": {"query": "memory"}}
    with patch.object(llm._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = response
        with patch.object(llm, "_parse_sse_tool_stream", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = (None, [tool_call])
            result = await llm.call_with_tools(
                messages=[{"role": "user", "content": "recall the memory"}],
                tools=TOOLS,
                tool_choice={"type": "function", "function": {"name": "recall"}},
                max_retries=0,
            )
        sent_payload = mock_post.call_args.kwargs["json"]

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "recall"
    assert sent_payload["tool_choice"] == {"type": "function", "name": "recall"}


@pytest.mark.asyncio
async def test_codex_lb_base_url_avoids_duplicate_codex_segment():
    llm = build_llm(api_key="lb-token", base_url="http://127.0.0.1:2455/backend-api/codex")
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

    assert sent_url == "http://127.0.0.1:2455/backend-api/codex/responses"
    assert sent_headers["Authorization"] == "Bearer lb-token"
    assert sent_headers["OpenAI-Account-ID"] == "account"
    assert "Origin" not in sent_headers


@pytest.mark.asyncio
async def test_codex_lb_uses_env_fallback_api_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(CODEX_LB_API_KEY_ENV, "env-lb-token")
    llm = build_llm(api_key=None, base_url="http://127.0.0.1:2455/backend-api")
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

    assert sent_url == "http://127.0.0.1:2455/backend-api/codex/responses"
    assert sent_headers["Authorization"] == "Bearer env-lb-token"
