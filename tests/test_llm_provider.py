import httpx
import pytest
from pydantic import BaseModel

from app.llm.provider import (
    LLMProviderError,
    Message,
    MockLLMProvider,
    OpenAICompatibleProvider,
)


class ExampleResponse(BaseModel):
    answer: str


@pytest.mark.asyncio
async def test_mock_provider_returns_typed_response() -> None:
    provider = MockLLMProvider([{"answer": "observed"}])

    response = await provider.generate_structured(
        [Message(role="user", content="Investigate")], ExampleResponse
    )

    assert response.answer == "observed"
    assert provider.requests[0][0].content == "Investigate"


@pytest.mark.asyncio
async def test_openai_compatible_provider_uses_configured_endpoint() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://llm.example/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer secret"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"answer":"evidence"}'}}]},
        )

    client = httpx.AsyncClient(
        base_url="https://llm.example/v1/", transport=httpx.MockTransport(handler)
    )
    provider = OpenAICompatibleProvider(
        api_key="secret", base_url="https://llm.example/v1", model="test-model", client=client
    )

    response = await provider.generate_structured(
        [Message(role="user", content="Investigate")], ExampleResponse
    )

    assert response.answer == "evidence"
    await client.aclose()


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ({"api_key": "", "base_url": "https://example.test/v1", "model": "model"}, "API_KEY"),
        ({"api_key": "key", "base_url": "", "model": "model"}, "BASE_URL"),
        ({"api_key": "key", "base_url": "https://example.test/v1", "model": ""}, "MODEL"),
    ],
)
def test_provider_requires_complete_configuration(
    values: dict[str, str], message: str
) -> None:
    with pytest.raises(LLMProviderError, match=message):
        OpenAICompatibleProvider(**values)


@pytest.mark.asyncio
async def test_provider_rejects_invalid_structured_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    client = httpx.AsyncClient(
        base_url="https://llm.example/v1/", transport=httpx.MockTransport(handler)
    )
    provider = OpenAICompatibleProvider(
        api_key="secret", base_url="https://llm.example/v1", model="test-model", client=client
    )

    with pytest.raises(LLMProviderError, match="required schema"):
        await provider.generate_structured(
            [Message(role="user", content="Investigate")], ExampleResponse
        )
    await client.aclose()


@pytest.mark.asyncio
async def test_empty_mock_queue_fails_clearly() -> None:
    provider = MockLLMProvider([])
    with pytest.raises(LLMProviderError, match="queue is empty"):
        await provider.generate_structured([], ExampleResponse)
