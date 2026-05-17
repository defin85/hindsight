"""
Shared transport foundation for Responses API style providers.

This base class implements the common HTTP/SSE request flow for providers that
talk to `/responses` endpoints, while leaving auth/header behavior and endpoint
resolution to provider-specific subclasses.
"""

import asyncio
import json
import logging
import time
from typing import Any

import httpx

from hindsight_api.engine.llm_interface import LLMInterface
from hindsight_api.engine.response_models import LLMToolCall, LLMToolCallResult, TokenUsage
from hindsight_api.metrics import get_metrics_collector

logger = logging.getLogger(__name__)


class ResponsesAPIBaseLLM(LLMInterface):
    """Reusable Responses API transport that is not tied to Codex auth."""

    def __init__(
        self,
        provider: str,
        api_key: str,
        base_url: str,
        model: str,
        reasoning_effort: str = "low",
        timeout: float = 120.0,
        **kwargs: Any,
    ):
        super().__init__(provider, api_key, base_url, model, reasoning_effort, **kwargs)
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=self.timeout)

    def _build_headers(self) -> dict[str, str]:
        """Build request headers for the provider."""
        raise NotImplementedError

    def _responses_url(self) -> str:
        """Build the final Responses API endpoint for the provider."""
        raise NotImplementedError

    def _auth_failure_message(self) -> str:
        """Return the provider-specific auth hint for 401/403 responses."""
        return "Responses API authentication failed. Check the configured API key and base URL."

    def _supports_reasoning_model(self) -> bool:
        """Return whether the configured model is likely to accept reasoning config."""
        model_lower = self.model.lower()
        return any(token in model_lower for token in ("gpt-5", "o1", "o3", "o4", "deepseek"))

    def _build_reasoning_config(self) -> dict[str, Any] | None:
        """Build provider-specific reasoning configuration."""
        if not self._supports_reasoning_model():
            return None
        return {"effort": self.reasoning_effort}

    def _extra_payload_fields(self) -> dict[str, Any]:
        """Provide provider-specific payload additions."""
        return {}

    def _normalize_tool_choice(self, tool_choice: str | dict[str, Any]) -> str | dict[str, Any]:
        """Normalize forced function tool choice for Responses-style payloads."""
        if not isinstance(tool_choice, dict):
            return tool_choice
        if str(tool_choice.get("type") or "").strip() != "function":
            return tool_choice
        function_payload = tool_choice.get("function")
        if isinstance(function_payload, dict):
            function_name = str(function_payload.get("name") or "").strip()
            if function_name:
                return {"type": "function", "name": function_name}
        function_name = str(tool_choice.get("name") or "").strip()
        if function_name:
            return {"type": "function", "name": function_name}
        return tool_choice

    def _prepare_messages(
        self,
        messages: list[dict[str, Any]],
        *,
        response_format: Any | None = None,
        strict_schema: bool = False,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Convert Hindsight's message abstraction into Responses API input items."""
        system_instruction = ""
        input_items: list[dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_instruction += ("\n\n" + content) if system_instruction else content
                continue

            if role == "tool":
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": msg.get("tool_call_id", ""),
                        "output": content,
                    }
                )
                continue

            if role == "assistant" and msg.get("tool_calls"):
                if content:
                    input_items.append({"role": "assistant", "content": content})
                for tool_call in msg.get("tool_calls") or []:
                    function_payload = tool_call.get("function", {})
                    arguments = function_payload.get("arguments", "{}")
                    if not isinstance(arguments, str):
                        arguments = json.dumps(arguments)
                    input_items.append(
                        {
                            "type": "function_call",
                            "call_id": tool_call.get("id", ""),
                            "name": function_payload.get("name", ""),
                            "arguments": arguments,
                        }
                    )
                continue

            input_items.append({"role": role, "content": content})

        if response_format is not None and hasattr(response_format, "model_json_schema"):
            schema = response_format.model_json_schema()
            schema_msg = f"\n\nYou must respond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"
            if strict_schema:
                schema_msg += "\nReturn only valid JSON with no markdown or extra commentary."
            system_instruction += schema_msg

        return system_instruction, input_items

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert OpenAI chat-completions style tools into Responses API tools."""
        converted = []
        for tool in tools:
            func = tool.get("function", {})
            converted.append(
                {
                    "type": "function",
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                }
            )
        return converted

    def _build_payload(
        self,
        *,
        messages: list[dict[str, Any]],
        response_format: Any | None = None,
        max_completion_tokens: int | None = None,
        strict_schema: bool = False,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] = "auto",
    ) -> dict[str, Any]:
        """Build the shared Responses API payload."""
        system_instruction, input_items = self._prepare_messages(
            messages,
            response_format=response_format,
            strict_schema=strict_schema,
        )
        payload: dict[str, Any] = {
            "model": self.model,
            "input": input_items,
            "store": False,
            "stream": True,
        }
        if system_instruction:
            payload["instructions"] = system_instruction
        if max_completion_tokens is not None:
            payload["max_output_tokens"] = max_completion_tokens
        reasoning = self._build_reasoning_config()
        if reasoning:
            payload["reasoning"] = reasoning
        if tools:
            payload["tools"] = self._convert_tools(tools)
            payload["tool_choice"] = self._normalize_tool_choice(tool_choice)
            payload["parallel_tool_calls"] = True
        payload.update(self._extra_payload_fields())
        return payload

    def _estimate_usage(self, messages: list[dict[str, Any]], content: str | None) -> TokenUsage:
        """Estimate usage for transports that do not report token counts."""
        estimated_input = sum(len(str(m.get("content", ""))) for m in messages) // 4
        estimated_output = len(content or "") // 4
        return TokenUsage(
            input_tokens=estimated_input,
            output_tokens=estimated_output,
            total_tokens=estimated_input + estimated_output,
        )

    def _serialize_result_for_trace(self, result: Any) -> str | None:
        """Serialize result for tracing without assuming a specific object type."""
        if result is None:
            return None
        if isinstance(result, str):
            return result
        if hasattr(result, "model_dump_json"):
            return result.model_dump_json()
        return json.dumps(result, ensure_ascii=False, default=str)

    async def verify_connection(self) -> None:
        """Verify Responses API connectivity by making a minimal text call."""
        try:
            logger.info(f"Verifying Responses API LLM: provider={self.provider}, model={self.model}")
            await self.call(
                messages=[{"role": "user", "content": "Say 'ok'"}],
                max_completion_tokens=10,
                max_retries=2,
                initial_backoff=0.5,
                max_backoff=2.0,
                scope="verification",
            )
            logger.info(f"Responses API LLM verified: {self.provider}/{self.model}")
        except Exception as e:
            raise RuntimeError(
                f"Responses API LLM connection verification failed for {self.provider}/{self.model}: {e}"
            ) from e

    async def call(
        self,
        messages: list[dict[str, str]],
        response_format: Any | None = None,
        max_completion_tokens: int | None = None,
        temperature: float | None = None,
        scope: str = "memory",
        max_retries: int = 10,
        initial_backoff: float = 1.0,
        max_backoff: float = 60.0,
        skip_validation: bool = False,
        strict_schema: bool = False,
        return_usage: bool = False,
    ) -> Any:
        """Make a streamed Responses API call and aggregate text output."""
        del temperature  # Responses transport does not expose temperature in the first cut.
        start_time = time.time()
        payload = self._build_payload(
            messages=messages,
            response_format=response_format,
            max_completion_tokens=max_completion_tokens,
            strict_schema=strict_schema,
        )
        headers = self._build_headers()
        url = self._responses_url()
        last_exception: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                response = await self._client.post(url, json=payload, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                content = await self._parse_sse_stream(response)

                if response_format is not None:
                    clean_content = content or ""
                    if "```json" in clean_content:
                        clean_content = clean_content.split("```json")[1].split("```")[0].strip()
                    elif "```" in clean_content:
                        clean_content = clean_content.split("```")[1].split("```")[0].strip()

                    json_data = json.loads(clean_content)
                    result = json_data if skip_validation else response_format.model_validate(json_data)
                else:
                    result = content

                duration = time.time() - start_time
                usage = self._estimate_usage(messages, content)
                metrics = get_metrics_collector()
                metrics.record_llm_call(
                    provider=self.provider,
                    model=self.model,
                    scope=scope,
                    duration=duration,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    success=True,
                )

                try:
                    from hindsight_api.tracing import get_span_recorder

                    span_recorder = get_span_recorder()
                    span_recorder.record_llm_call(
                        provider=self.provider,
                        model=self.model,
                        scope=scope,
                        messages=messages,
                        response_content=self._serialize_result_for_trace(result),
                        input_tokens=usage.input_tokens,
                        output_tokens=usage.output_tokens,
                        duration=duration,
                        finish_reason=None,
                        error=None,
                    )
                except Exception:
                    pass

                if return_usage:
                    return result, usage
                return result

            except httpx.HTTPStatusError as e:
                last_exception = e
                status_code = e.response.status_code
                if status_code in (401, 403):
                    logger.error(f"Responses API auth error (HTTP {status_code}): {e.response.text[:200]}")
                    raise RuntimeError(self._auth_failure_message()) from e
                error_detail = e.response.text[:500] if hasattr(e.response, "text") else str(e)
                if attempt < max_retries:
                    backoff = min(initial_backoff * (2**attempt), max_backoff)
                    logger.warning(
                        f"Responses API HTTP error {status_code} (attempt {attempt + 1}/{max_retries + 1}): {error_detail}"
                    )
                    await asyncio.sleep(backoff)
                    continue
                logger.error(
                    f"Responses API HTTP error after {max_retries + 1} attempts: Status {status_code}, Detail: {error_detail}"
                )
                raise

            except httpx.RequestError as e:
                last_exception = e
                if attempt < max_retries:
                    backoff = min(initial_backoff * (2**attempt), max_backoff)
                    logger.warning(f"Responses API connection error (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    await asyncio.sleep(backoff)
                    continue
                logger.error(f"Responses API connection error after {max_retries + 1} attempts: {e}")
                raise

            except json.JSONDecodeError as e:
                last_exception = e
                if attempt < max_retries:
                    backoff = min(initial_backoff * (2**attempt), max_backoff)
                    logger.warning(f"Responses API JSON parse error (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    await asyncio.sleep(backoff)
                    continue
                raise

            except Exception as e:
                logger.error(f"Unexpected Responses API error: {type(e).__name__}: {e}")
                raise

        if last_exception:
            raise last_exception
        raise RuntimeError("Responses API call failed after all retries")

    async def _parse_sse_stream(self, response: httpx.Response) -> str:
        """Parse streamed text events from a Responses API event stream."""
        full_text = ""
        event_type = None

        async for line in response.aiter_lines():
            if not line:
                continue

            if line.startswith("event: "):
                event_type = line[7:]
                continue

            if not line.startswith("data: "):
                continue

            data_str = line[6:]
            if data_str == "[DONE]":
                break

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            current_event = event_type or data.get("type")
            if current_event in ("response.output_text.delta", "response.text.delta", "response.content_part.delta"):
                full_text += data.get("delta", "")
            elif current_event in ("response.output_text.done", "response.text.done") and not full_text:
                full_text = data.get("text", "")
            elif current_event == "response.output_item.done" and not full_text:
                item = data.get("item", {})
                if item.get("type") == "message":
                    for part in item.get("content") or []:
                        if isinstance(part, dict) and part.get("type") in ("output_text", "text") and "text" in part:
                            full_text += part["text"]

        return full_text

    async def call_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_completion_tokens: int | None = None,
        temperature: float | None = None,
        scope: str = "tools",
        max_retries: int = 5,
        initial_backoff: float = 1.0,
        max_backoff: float = 30.0,
        tool_choice: str | dict[str, Any] = "auto",
    ) -> LLMToolCallResult:
        """Make a streamed Responses API tool call request."""
        del temperature  # Responses transport does not expose temperature in the first cut.
        start_time = time.time()
        payload = self._build_payload(
            messages=messages,
            max_completion_tokens=max_completion_tokens,
            tools=tools,
            tool_choice=tool_choice,
        )
        headers = self._build_headers()
        url = self._responses_url()
        last_exception: Exception | None = None

        for attempt in range(max_retries + 1):
            try:
                response = await self._client.post(url, json=payload, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                content, tool_calls = await self._parse_sse_tool_stream(response)

                duration = time.time() - start_time
                usage = self._estimate_usage(messages, content)
                metrics = get_metrics_collector()
                metrics.record_llm_call(
                    provider=self.provider,
                    model=self.model,
                    scope=scope,
                    duration=duration,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    success=True,
                )

                try:
                    from hindsight_api.tracing import get_span_recorder

                    span_recorder = get_span_recorder()
                    tool_calls_dict = (
                        [{"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in tool_calls]
                        if tool_calls
                        else None
                    )
                    span_recorder.record_llm_call(
                        provider=self.provider,
                        model=self.model,
                        scope=scope,
                        messages=messages,
                        response_content=content,
                        input_tokens=usage.input_tokens,
                        output_tokens=usage.output_tokens,
                        duration=duration,
                        finish_reason="tool_calls" if tool_calls else "stop",
                        error=None,
                        tool_calls=tool_calls_dict,
                    )
                except Exception:
                    pass

                return LLMToolCallResult(
                    content=content,
                    tool_calls=tool_calls,
                    finish_reason="tool_calls" if tool_calls else "stop",
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                )

            except httpx.HTTPStatusError as e:
                last_exception = e
                status_code = e.response.status_code
                if status_code in (401, 403):
                    logger.error(f"Responses API auth error (HTTP {status_code}): {e.response.text[:200]}")
                    raise RuntimeError(self._auth_failure_message()) from e
                error_detail = e.response.text[:500] if hasattr(e.response, "text") else str(e)
                if attempt < max_retries:
                    backoff = min(initial_backoff * (2**attempt), max_backoff)
                    logger.warning(
                        f"Responses API tool HTTP error {status_code} (attempt {attempt + 1}/{max_retries + 1}): {error_detail}"
                    )
                    await asyncio.sleep(backoff)
                    continue
                logger.error(
                    f"Responses API tool HTTP error after {max_retries + 1} attempts: Status {status_code}, Detail: {error_detail}"
                )
                raise

            except httpx.RequestError as e:
                last_exception = e
                if attempt < max_retries:
                    backoff = min(initial_backoff * (2**attempt), max_backoff)
                    logger.warning(
                        f"Responses API tool connection error (attempt {attempt + 1}/{max_retries + 1}): {e}"
                    )
                    await asyncio.sleep(backoff)
                    continue
                logger.error(f"Responses API tool connection error after {max_retries + 1} attempts: {e}")
                raise

            except Exception as e:
                logger.error(f"Responses API tool call error: {e}")
                raise

        if last_exception:
            raise last_exception
        raise RuntimeError("Responses API tool call failed after all retries")

    async def _parse_sse_tool_stream(self, response: httpx.Response) -> tuple[str | None, list[LLMToolCall]]:
        """Parse streamed Responses API content and completed function calls."""
        content = ""
        event_type = None
        tool_calls: list[LLMToolCall] = []
        seen_call_ids: set[str] = set()

        async for line in response.aiter_lines():
            if not line:
                continue

            if line.startswith("event: "):
                event_type = line[7:]
                continue

            if not line.startswith("data: "):
                continue

            data_str = line[6:]
            if data_str == "[DONE]":
                break

            try:
                data = json.loads(data_str)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Responses API SSE data: {e}, data_str: {data_str[:200]}")
                continue

            current_event = event_type or data.get("type")
            if current_event in ("response.output_text.delta", "response.text.delta", "response.content_part.delta"):
                content += data.get("delta", "")
                continue

            if current_event == "response.function_call_arguments.done":
                call_id = data.get("call_id", "")
                if call_id and call_id not in seen_call_ids:
                    arguments_str = data.get("arguments", "{}")
                    try:
                        arguments = json.loads(arguments_str)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse tool arguments: {arguments_str}")
                        arguments = {}
                    tool_calls.append(
                        LLMToolCall(
                            id=call_id,
                            name=data.get("name", ""),
                            arguments=arguments,
                        )
                    )
                    seen_call_ids.add(call_id)
                continue

            if current_event != "response.output_item.done":
                continue

            item = data.get("item", {})
            item_type = item.get("type")
            if item_type == "function_call" and item.get("status") == "completed":
                call_id = item.get("call_id", "")
                if call_id in seen_call_ids:
                    continue
                arguments_str = item.get("arguments", "{}")
                try:
                    arguments = json.loads(arguments_str)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse tool arguments: {arguments_str}")
                    arguments = {}
                tool_calls.append(
                    LLMToolCall(
                        id=call_id,
                        name=item.get("name", ""),
                        arguments=arguments,
                    )
                )
                seen_call_ids.add(call_id)
            elif item_type == "message" and not content:
                for part in item.get("content") or []:
                    if isinstance(part, dict) and part.get("type") in ("output_text", "text") and "text" in part:
                        content += part["text"]

        return content if content else None, tool_calls

    async def cleanup(self) -> None:
        """Close the shared HTTP client."""
        await self._client.aclose()
