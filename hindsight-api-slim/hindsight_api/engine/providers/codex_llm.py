"""
OpenAI Codex LLM provider using ChatGPT Plus/Pro OAuth authentication.

This provider enables using ChatGPT Plus/Pro subscriptions for API calls
without separate OpenAI Platform API credits. It uses OAuth tokens from
~/.codex/auth.json and communicates with the ChatGPT backend API.
"""

import json
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .responses_api_base import ResponsesAPIBaseLLM

logger = logging.getLogger(__name__)
CODEX_DEFAULT_BASE_URL = "https://chatgpt.com/backend-api"
CODEX_LB_API_KEY_ENV = "CODEX_LB_API_KEY"


@dataclass(frozen=True)
class CodexOAuthCredentials:
    """OAuth credentials read from the Codex CLI auth file."""

    access_token: str
    account_id: str | None


class CodexLLM(ResponsesAPIBaseLLM):
    """
    LLM provider using OpenAI Codex OAuth authentication.

    Authenticates using ChatGPT Plus/Pro credentials stored in ~/.codex/auth.json
    and makes API calls to chatgpt.com/backend-api/codex/responses.

    When a custom base URL is configured, the same request shape can also be sent
    through a local Codex load balancer. That transport uses a separate bearer
    token (`HINDSIGHT_API_LLM_API_KEY` or `CODEX_LB_API_KEY`) while preserving
    the Codex OAuth metadata required by the upstream backend.
    """

    def __init__(
        self,
        provider: str,
        api_key: str,  # Ignored for direct Codex auth; used for local transport auth.
        base_url: str,
        model: str,
        reasoning_effort: str = "low",
        **kwargs: Any,
    ):
        super().__init__(
            provider=provider,
            api_key=api_key,
            base_url=base_url or CODEX_DEFAULT_BASE_URL,
            model=model,
            reasoning_effort=reasoning_effort,
            **kwargs,
        )

        try:
            oauth_credentials = self._load_codex_auth()
            self.access_token = oauth_credentials.access_token
            self.account_id = oauth_credentials.account_id
            logger.info(f"Loaded Codex OAuth credentials for account: {self.account_id}")
        except Exception as e:
            raise RuntimeError(
                f"Failed to load Codex OAuth credentials from ~/.codex/auth.json: {e}\n\n"
                "To set up Codex authentication:\n"
                "1. Install Codex CLI: npm install -g @openai/codex\n"
                "2. Login: codex auth login\n"
                "3. Verify: ls ~/.codex/auth.json\n\n"
                "Or use a different provider (openai, anthropic, gemini) with API keys."
            ) from e

        self._uses_chatgpt_backend = self._is_chatgpt_backend(self.base_url)
        self._request_bearer_token = self._resolve_request_bearer_token(api_key)

        if self.model.startswith("openai/"):
            self.model = self.model[len("openai/") :]

    def _load_codex_auth(self) -> CodexOAuthCredentials:
        """
        Load OAuth credentials from ~/.codex/auth.json.

        Raises:
            FileNotFoundError: If auth file doesn't exist.
            ValueError: If auth file is invalid.
        """
        auth_file = Path.home() / ".codex" / "auth.json"

        if not auth_file.exists():
            raise FileNotFoundError(
                f"Codex auth file not found: {auth_file}\nRun 'codex auth login' to authenticate with ChatGPT Plus/Pro."
            )

        with open(auth_file) as f:
            data = json.load(f)

        auth_mode = data.get("auth_mode")
        if auth_mode != "chatgpt":
            raise ValueError(f"Expected auth_mode='chatgpt', got: {auth_mode}")

        tokens = data.get("tokens", {})
        access_token = tokens.get("access_token")
        account_id = tokens.get("account_id")

        if not access_token:
            raise ValueError("No access_token found in Codex auth file. Run 'codex auth login' again.")

        return CodexOAuthCredentials(access_token=access_token, account_id=account_id)

    def _is_chatgpt_backend(self, base_url: str) -> bool:
        """Detect the canonical ChatGPT backend versus a local Codex proxy."""
        return urlparse(base_url).netloc == "chatgpt.com"

    def _resolve_request_bearer_token(self, provided_api_key: str | None) -> str:
        """
        Choose the bearer token for HTTP transport.

        Standard Codex requests authenticate directly against ChatGPT with the
        OAuth access token. Local codex-lb deployments sit in front of that
        backend and require their own API key, so prefer the explicit
        Hindsight key (or CODEX_LB_API_KEY fallback) when a custom base URL is
        configured.
        """
        if self._uses_chatgpt_backend:
            return self.access_token

        provided_token = (provided_api_key or "").strip()
        if provided_token:
            return provided_token

        env_token = os.getenv(CODEX_LB_API_KEY_ENV, "").strip()
        if env_token:
            return env_token

        return self.access_token

    def _build_headers(self) -> dict[str, str]:
        """Build headers for either direct Codex or codex-lb transport."""
        headers = {
            "Authorization": f"Bearer {self._request_bearer_token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        }
        if self.account_id:
            headers["OpenAI-Account-ID"] = self.account_id
        if self._uses_chatgpt_backend:
            headers["Origin"] = "https://chatgpt.com"
        return headers

    def _responses_url(self) -> str:
        """
        Build the final Responses endpoint for direct Codex and local codex-lb.

        Hindsight historically accepted the ChatGPT backend root
        (`.../backend-api`) and appended `/codex/responses` itself. Local
        codex-lb configs often already end in `/backend-api/codex`, so blindly
        appending the old suffix would produce `/codex/codex/responses`.
        """
        normalized_base_url = self.base_url.rstrip("/")
        if normalized_base_url.endswith("/codex/responses"):
            return normalized_base_url
        if normalized_base_url.endswith("/codex"):
            return f"{normalized_base_url}/responses"
        return f"{normalized_base_url}/codex/responses"

    def _auth_failure_message(self) -> str:
        """Return the most useful auth hint for the active transport."""
        if self._request_bearer_token != self.access_token:
            return (
                "Codex authentication failed. The configured codex-lb token was rejected.\n"
                "Set HINDSIGHT_API_LLM_API_KEY (or CODEX_LB_API_KEY) to a valid local transport token."
            )
        return "Codex authentication failed. Your OAuth token may have expired.\nRun 'codex auth login' to re-authenticate."

    def _map_reasoning_effort(self, effort: str) -> str:
        """
        Map standard reasoning effort to Codex reasoning summary format.

        Args:
            effort: Standard effort level ("low", "medium", "high", "xhigh").

        Returns:
            Codex reasoning summary: "concise", "detailed", or "auto".
        """
        mapping = {
            "low": "concise",
            "medium": "auto",
            "high": "detailed",
            "xhigh": "detailed",
        }
        return mapping.get(effort.lower(), "auto")

    def _build_reasoning_config(self) -> dict[str, Any] | None:
        """Build Codex-specific reasoning summary payload."""
        reasoning_summary = "detailed" if "5.2" in self.model else self._map_reasoning_effort(self.reasoning_effort)
        return {"summary": reasoning_summary}

    def _extra_payload_fields(self) -> dict[str, Any]:
        """Add Codex-specific payload fields required by the backend."""
        return {
            "include": ["reasoning.encrypted_content"],
            "prompt_cache_key": str(uuid.uuid4()),
        }

    def _prepare_messages(
        self,
        messages: list[dict[str, Any]],
        *,
        response_format: Any | None = None,
        strict_schema: bool = False,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Preserve the historical Codex message shaping during the transport refactor.

        Codex accepted input items in the custom ChatGPT backend shape
        `{"type": "message", "role": ..., "content": ...}` and tool outputs were
        fed back as plain user messages rather than formal function_call_output
        items. Keep that behavior stable while reusing the shared transport.
        """
        system_instruction = ""
        user_messages: list[dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_instruction += ("\n\n" + content) if system_instruction else content
            elif role == "tool":
                user_messages.append(
                    {
                        "type": "message",
                        "role": "user",
                        "content": f"Tool result: {content}",
                    }
                )
            else:
                user_messages.append(
                    {
                        "type": "message",
                        "role": role,
                        "content": content,
                    }
                )

        if response_format is not None and hasattr(response_format, "model_json_schema"):
            schema = response_format.model_json_schema()
            schema_msg = f"\n\nYou must respond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"
            if strict_schema:
                schema_msg += "\nReturn only valid JSON with no markdown or extra commentary."
            system_instruction += schema_msg

        return system_instruction, user_messages

    async def verify_connection(self) -> None:
        """Verify Codex connection by making a simple test call."""
        try:
            logger.info(f"Verifying Codex LLM: model={self.model}, account={self.account_id}...")
            await self.call(
                messages=[{"role": "user", "content": "Say 'ok'"}],
                max_completion_tokens=10,
                max_retries=2,
                initial_backoff=0.5,
                max_backoff=2.0,
                scope="verification",
            )
            logger.info(f"Codex LLM verified: {self.model}")
        except Exception as e:
            if "429" in str(e) or "usage_limit_reached" in str(e):
                logger.warning(f"Codex LLM quota exhausted for {self.model}, continuing startup: {e}")
                return
            raise RuntimeError(f"Codex LLM connection verification failed for {self.model}: {e}") from e
