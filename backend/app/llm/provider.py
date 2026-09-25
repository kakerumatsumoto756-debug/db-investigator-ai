import json
from collections import deque
from collections.abc import Sequence
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings

ResponseModel = TypeVar("ResponseModel", bound=BaseModel)


class LLMProviderError(RuntimeError):
    """A sanitized model-provider failure suitable for application error handling."""


class Message(BaseModel):
    role: str
    content: str


class LLMProvider(Protocol):
    async def generate_structured(
        self,
        messages: Sequence[Message],
        response_type: type[ResponseModel],
    ) -> ResponseModel: ...

    async def close(self) -> None: ...


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 60,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise LLMProviderError("LLM_API_KEY is required")
        if not base_url:
            raise LLMProviderError("LLM_BASE_URL is required")
        if not model:
            raise LLMProviderError("LLM_MODEL is required")
        self._model = model
        self._authorization = f"Bearer {api_key}"
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_seconds,
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenAICompatibleProvider":
        return cls(
            api_key=settings.llm_api_key.get_secret_value(),
            base_url=settings.llm_base_url,
            model=settings.llm_model,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def generate_structured(
        self,
        messages: Sequence[Message],
        response_type: type[ResponseModel],
    ) -> ResponseModel:
        schema_instruction = (
            "Return one JSON object matching this JSON Schema. Do not include markdown or text "
            f"outside the object:\n{json.dumps(response_type.model_json_schema())}"
        )
        request_messages = [message.model_dump() for message in messages]
        request_messages.append({"role": "system", "content": schema_instruction})

        try:
            response = await self._client.post(
                "chat/completions",
                headers={"Authorization": self._authorization},
                json={
                    "model": self._model,
                    "messages": request_messages,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            return response_type.model_validate_json(content)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMProviderError("The configured LLM provider returned an invalid response") from exc
        except ValidationError as exc:
            raise LLMProviderError("The LLM response did not match the required schema") from exc


class MockLLMProvider:
    """Queue-backed provider for repeatable tests and local demonstrations."""

    def __init__(self, responses: Sequence[BaseModel | dict[str, Any]]) -> None:
        self._responses: deque[BaseModel | dict[str, Any]] = deque(responses)
        self.requests: list[list[Message]] = []

    async def generate_structured(
        self,
        messages: Sequence[Message],
        response_type: type[ResponseModel],
    ) -> ResponseModel:
        self.requests.append(list(messages))
        if not self._responses:
            raise LLMProviderError("Mock LLM response queue is empty")
        response = self._responses.popleft()
        if isinstance(response, BaseModel):
            response = response.model_dump()
        return response_type.model_validate(response)

    async def close(self) -> None:
        return None
