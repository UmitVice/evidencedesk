import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from evidencedesk.config import settings
from evidencedesk.errors import DomainError
from evidencedesk.models import Answer
from evidencedesk.providers import (
    CompositeProvider,
    FallbackGenerator,
    FixtureProvider,
    OpenAICompatibleGenerator,
    answer_json_schema,
    build_messages,
    run_sync,
)
from evidencedesk.voice.gateway import _authenticate_ws

SOURCE = {"id": str(uuid4()), "body": "Webhooks retry after 1 minute, 5 minutes, and 30 minutes."}
TICKET = {"body": "Our webhook stopped. How do retries work?"}
ANSWER = Answer.model_validate(
    {
        "status": "answered",
        "claims": [
            {
                "text": "Webhooks retry three times.",
                "citations": [
                    {"source_id": SOURCE["id"], "quote": "retry after 1 minute, 5 minutes"}
                ],
            }
        ],
        "proposed_note": "Check the retry schedule.",
    }
)


def completion(content: str) -> dict:
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 900, "completion_tokens": 120},
    }


def test_openai_compatible_generator_sends_constrained_schema():
    seen: dict = {}

    def respond(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=completion(ANSWER.model_dump_json()))

    generator = OpenAICompatibleGenerator(
        "http://127.0.0.1:8080/v1", "evidencedesk-gemma", "local-key",
        transport=httpx.MockTransport(respond),
    )
    raw, usage = generator.generate(TICKET, "", [SOURCE])

    assert Answer.model_validate_json(raw) == ANSWER
    assert usage == {"prompt_tokens": 900, "completion_tokens": 120}
    assert generator.model_id == "evidencedesk-gemma"
    assert seen["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    assert seen["auth"] == "Bearer local-key"
    assert seen["body"]["messages"] == build_messages(TICKET, "", [SOURCE])
    assert seen["body"]["temperature"] == 0
    assert seen["body"]["chat_template_kwargs"] == {"enable_thinking": False}
    schema = seen["body"]["response_format"]["json_schema"]["schema"]
    answered = schema["anyOf"][0]["properties"]["claims"]["items"]
    assert answered["properties"]["citations"]["items"]["properties"]["source_id"]["enum"] == [
        SOURCE["id"]
    ]


def test_answer_schema_restricts_abstention_shape():
    abstain = answer_json_schema(["a"])["anyOf"][1]["properties"]
    assert abstain["status"] == {"const": "insufficient_evidence"}
    assert abstain["claims"]["maxItems"] == 0
    assert abstain["proposed_note"] == {"type": "null"}


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx.Response(503, text="secret"), "provider_transient"),
        (httpx.Response(429), "provider_quota"),
        (httpx.Response(401), "provider_unavailable"),
        (httpx.Response(200, json={"choices": []}), "provider_invalid"),
        (httpx.Response(200, json=completion("   ")), "provider_invalid"),
    ],
)
def test_openai_compatible_errors_are_sanitized(response, code):
    generator = OpenAICompatibleGenerator(
        "http://127.0.0.1:8080/v1", "m", transport=httpx.MockTransport(lambda _: response)
    )
    with pytest.raises(DomainError) as error:
        generator.generate(TICKET, "", [SOURCE])
    assert error.value.code == code
    assert "secret" not in error.value.message


def test_openai_compatible_requires_http_base_url():
    with pytest.raises(DomainError) as error:
        OpenAICompatibleGenerator("", "m")
    assert error.value.code == "provider_unavailable"


class Failing:
    model_id = "primary"

    def __init__(self, code: str):
        self.code = code

    def generate(self, ticket, question, evidence):
        raise DomainError(self.code, "failure", 503)


class Fixed:
    model_id = "fallback"

    def generate(self, ticket, question, evidence):
        return ANSWER.model_dump_json(), None


def test_fallback_generator_switches_on_provider_failure():
    generator = FallbackGenerator(Failing("provider_timeout"), Fixed())
    raw, _ = generator.generate(TICKET, "", [SOURCE])
    assert Answer.model_validate_json(raw) == ANSWER
    assert generator.model_id == "fallback"
    assert generator.fell_back


def test_fallback_generator_does_not_hide_non_provider_errors():
    generator = FallbackGenerator(Failing("ai_disabled"), Fixed())
    with pytest.raises(DomainError):
        generator.generate(TICKET, "", [SOURCE])
    assert generator.model_id == "primary"


def test_composite_provider_reports_serving_model():
    generator = FallbackGenerator(Failing("provider_transient"), Fixed())
    composite = CompositeProvider(FixtureProvider(), generator)
    assert composite.manifest == FixtureProvider.manifest
    composite.generate(TICKET, "", [SOURCE])
    assert composite.model_id == "fallback"


def test_run_sync_works_inside_a_running_event_loop():
    async def value() -> int:
        await asyncio.sleep(0)
        return 7

    async def caller() -> int:
        return run_sync(value())

    assert run_sync(value()) == 7
    assert asyncio.run(caller()) == 7


def test_voice_gateway_fails_closed_without_service_key(monkeypatch):
    monkeypatch.setenv("SERVICE_KEY", "")
    settings.cache_clear()
    try:
        assert _authenticate_ws("x" * 43, "") is None
        assert _authenticate_ws("x" * 43, "anything") is None
    finally:
        settings.cache_clear()


def test_local_embedder_has_its_own_manifest(monkeypatch):
    from evidencedesk.providers import (
        LIVE_MANIFEST,
        LOCAL_MANIFEST,
        CloudflareProvider,
        LocalEmbedder,
        embedder,
        provider,
    )

    monkeypatch.setenv("AI_MODE", "live")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    settings.cache_clear()
    try:
        assert isinstance(embedder(), LocalEmbedder)
        assert LOCAL_MANIFEST != LIVE_MANIFEST
        composite = provider()
        assert composite.manifest == LOCAL_MANIFEST
        assert composite.model_id == CloudflareProvider.model_id
    finally:
        settings.cache_clear()


def test_prompt_keeps_non_ascii_text_literal():
    source = {"id": str(uuid4()), "body": "Çekim işlemleri 24 saat içinde onaylanır."}
    user = build_messages({"body": "Çekim ne zaman onaylanır?"}, "", [source])[1]["content"]
    assert "Çekim işlemleri 24 saat içinde onaylanır." in user
    assert "\\u" not in user


def test_openai_compatible_generator_reports_the_served_model():
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={**completion(ANSWER.model_dump_json()), "model": "base"})

    generator = OpenAICompatibleGenerator(
        "http://127.0.0.1:8080/v1", "requested-lora", transport=httpx.MockTransport(respond)
    )
    generator.generate(TICKET, "", [SOURCE])
    assert generator.model_id == "base"


def test_prompt_lists_relations_only_between_passages_in_context():
    current, legacy = str(uuid4()), str(uuid4())
    relation = {"document_id": "d", "source_id": "limits", "title": "Limits", "version": 2}
    evidence = [
        {"id": current, "body": "Current text.", "relations": []},
        {
            "id": legacy,
            "body": "Legacy text.",
            "relations": [
                {**relation, "relation": "superseded_by", "evidence_id": current},
                {**relation, "relation": "see_also", "evidence_id": current},
                {**relation, "relation": "conflicts_with", "evidence_id": None},
            ],
        },
    ]
    context = json.loads(build_messages(TICKET, "", evidence)[1]["content"])["evidence"]
    assert "relations" not in context[0]
    assert context[1]["relations"] == [{"relation": "superseded_by", "source_id": current}]


def test_truncated_generations_are_retryable_not_validated():
    capped = completion(ANSWER.model_dump_json()[:40])
    capped["usage"]["completion_tokens"] = 700
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=capped))
    generator = OpenAICompatibleGenerator("http://127.0.0.1:8080/v1", "m", transport=transport)
    with pytest.raises(DomainError) as error:
        generator.generate(TICKET, "", [SOURCE])
    assert error.value.code == "generation_truncated"

    stopped = completion(ANSWER.model_dump_json())
    stopped["choices"][0]["finish_reason"] = "length"
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json=stopped))
    generator = OpenAICompatibleGenerator("http://127.0.0.1:8080/v1", "m", transport=transport)
    with pytest.raises(DomainError) as error:
        generator.generate(TICKET, "", [SOURCE])
    assert error.value.code == "generation_truncated"


def test_cloudflare_truncation_is_retryable(monkeypatch):
    from evidencedesk.providers import CloudflareProvider

    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a" * 32)
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-token")
    settings.cache_clear()
    body = {"success": True, "result": {"response": '{"status":"answered","claims":[',
                                        "usage": {"completion_tokens": 700}}}
    adapter = CloudflareProvider(httpx.MockTransport(lambda _: httpx.Response(200, json=body)))
    try:
        with pytest.raises(DomainError) as error:
            adapter.generate(TICKET, "", [SOURCE])
        assert error.value.code == "generation_truncated"
    finally:
        settings.cache_clear()


def test_fallback_covers_truncation():
    generator = FallbackGenerator(Failing("generation_truncated"), Fixed())
    generator.generate(TICKET, "", [SOURCE])
    assert generator.model_id == "fallback"
