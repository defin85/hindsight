"""Generic provider for Responses API-compatible endpoints."""

from typing import Any

from .responses_api_base import ResponsesAPIBaseLLM

DEFAULT_RESPONSES_API_BASE_URL = "https://api.openai.com/v1"


class ResponsesAPILLM(ResponsesAPIBaseLLM):
    """Responses API provider using explicit API key and base URL."""

    def __init__(
        self,
        provider: str,
        api_key: str,
        base_url: str,
        model: str,
        reasoning_effort: str = "low",
        **kwargs: Any,
    ):
        super().__init__(
            provider=provider,
            api_key=api_key,
            base_url=base_url or DEFAULT_RESPONSES_API_BASE_URL,
            model=model,
            reasoning_effort=reasoning_effort,
            **kwargs,
        )

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _responses_url(self) -> str:
        normalized_base_url = self.base_url.rstrip("/")
        if normalized_base_url.endswith("/responses"):
            return normalized_base_url
        return f"{normalized_base_url}/responses"

    def _auth_failure_message(self) -> str:
        return "Responses API authentication failed. Check HINDSIGHT_API_LLM_API_KEY and HINDSIGHT_API_LLM_BASE_URL."
