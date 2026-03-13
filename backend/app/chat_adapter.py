import json
import os
from dataclasses import dataclass
from typing import Protocol

import requests


class ChatAdapterError(Exception):
    """Base error for grounded chat adapter failures."""


class ChatAdapterNotConfiguredError(ChatAdapterError):
    """Raised when the app has no usable LLM configuration."""


@dataclass
class ChatCompletionResult:
    """Structured chat output expected from the configured LLM adapter."""

    answer: str
    citation_ids: list[str]


class ChatAdapter(Protocol):
    """Boundary for hosted or local chat backends."""

    model_name: str

    def answer(self, *, system_prompt: str, user_prompt: str) -> ChatCompletionResult:
        """Return one grounded answer plus citation ids."""


class OpenAICompatibleChatAdapter:
    """Small adapter for OpenAI-compatible chat completion endpoints."""

    def __init__(self, *, base_url: str, model_name: str, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.api_key = api_key

    def answer(self, *, system_prompt: str, user_prompt: str) -> ChatCompletionResult:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model_name,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise ChatAdapterError("The configured chat model could not be reached.") from error

        try:
            response_payload = response.json()
            content = response_payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
            raise ChatAdapterError("The chat model returned an unreadable response.") from error

        return parse_chat_completion(content)


def parse_chat_completion(content: str) -> ChatCompletionResult:
    """Parse the adapter response as strict JSON for predictable grounding."""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as error:
        raise ChatAdapterError("The chat model did not return valid JSON.") from error

    answer = str(payload.get("answer", "")).strip()
    raw_citations = payload.get("citation_ids", [])
    citation_ids = [str(citation).strip() for citation in raw_citations if str(citation).strip()]

    if not answer:
        raise ChatAdapterError("The chat model returned an empty answer.")

    return ChatCompletionResult(answer=answer, citation_ids=citation_ids)


def get_default_chat_adapter() -> ChatAdapter:
    """Create the one configured adapter for this phase."""
    model_name = os.getenv("GC_LLM_MODEL", "").strip()
    base_url = os.getenv("GC_LLM_BASE_URL", "https://api.openai.com/v1").strip()
    api_key = os.getenv("GC_LLM_API_KEY", "").strip() or None

    if not model_name:
        raise ChatAdapterNotConfiguredError(
            "No chat model is configured. Set GC_LLM_MODEL and restart the backend."
        )

    if "api.openai.com" in base_url and not api_key:
        raise ChatAdapterNotConfiguredError(
            "No chat model is configured. Set GC_LLM_API_KEY for the configured hosted model."
        )

    return OpenAICompatibleChatAdapter(
        base_url=base_url,
        model_name=model_name,
        api_key=api_key,
    )
