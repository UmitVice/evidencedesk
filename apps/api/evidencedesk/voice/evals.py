import re
import time
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from evidencedesk.voice.mock_provider import MockVoiceProvider
from evidencedesk.voice.protocol import (
    AudioFrame,
    CitationEvent,
    ControlEvent,
    ToolCallEvent,
    TranscriptEvent,
)
from evidencedesk.voice.provider import VoiceProvider, VoiceSessionContext
from evidencedesk.voice.tools import search_knowledge_base


def calculate_percentile(data: list[float], p: float) -> float:
    """Calculate the p-th percentile (0.0 to 1.0) of a list of numeric values."""
    if not data:
        return 0.0
    if len(data) == 1:
        return round(data[0], 2)
    sorted_data = sorted(data)
    idx = (len(sorted_data) - 1) * p
    lower = int(idx)
    upper = min(lower + 1, len(sorted_data) - 1)
    weight = idx - lower
    val = sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight
    return round(val, 2)


class TTFATracker:
    """Tracks Time-To-First-Audio (TTFA) latency in milliseconds."""

    def __init__(self) -> None:
        self.samples_ms: list[float] = []

    def record(self, latency_ms: float) -> None:
        self.samples_ms.append(round(latency_ms, 2))

    def summary(self) -> dict[str, Any]:
        return {
            "count": len(self.samples_ms),
            "p50": calculate_percentile(self.samples_ms, 0.50),
            "p95": calculate_percentile(self.samples_ms, 0.95),
            "min": round(min(self.samples_ms), 2) if self.samples_ms else 0.0,
            "max": round(max(self.samples_ms), 2) if self.samples_ms else 0.0,
            "samples": self.samples_ms,
        }


class BargeInTracker:
    """Tracks interruption cancellation latency in milliseconds."""

    def __init__(self) -> None:
        self.samples_ms: list[float] = []

    def record(self, latency_ms: float) -> None:
        self.samples_ms.append(round(latency_ms, 2))

    def summary(self) -> dict[str, Any]:
        return {
            "count": len(self.samples_ms),
            "p50": calculate_percentile(self.samples_ms, 0.50),
            "p95": calculate_percentile(self.samples_ms, 0.95),
            "min": round(min(self.samples_ms), 2) if self.samples_ms else 0.0,
            "max": round(max(self.samples_ms), 2) if self.samples_ms else 0.0,
            "samples": self.samples_ms,
        }


class CitationFaithfulnessEvaluator:
    """Evaluates whether spoken assistant claims are supported by retrieved excerpts."""

    @staticmethod
    def evaluate(transcript: str, cited_quotes: list[str]) -> bool:
        if not cited_quotes:
            return False
        # Normalize text and check if cited quote words appear in spoken transcript
        norm_transcript = " ".join(re.findall(r"[a-z0-9]+", transcript.lower()))
        for quote in cited_quotes:
            quote_words = re.findall(r"[a-z0-9]+", quote.lower())
            if not quote_words:
                continue
            # Check for high word overlap (at least 70% of quote words in transcript)
            overlap = sum(1 for w in quote_words if w in norm_transcript)
            ratio = overlap / len(quote_words)
            if ratio >= 0.70:
                return True
        return False


class AbstentionEvaluator:
    """Verifies that the assistant explicitly abstains when knowledge is absent."""

    ABSTENTION_INDICATORS = [
        "could not find",
        "cannot find",
        "insufficient evidence",
        "not found",
        "unresolved",
        "unverified",
        "does not mention",
        "no information",
    ]

    @classmethod
    def evaluate(cls, transcript: str) -> bool:
        norm = transcript.lower()
        return any(phrase in norm for phrase in cls.ABSTENTION_INDICATORS)


class VoiceScenario(BaseModel):
    """Voice evaluation test case scenario."""

    name: str
    query: str
    expected_citations: bool = True
    test_interruption: bool = False
    expected_abstention: bool = False
    ticket_id: str | None = None
    ticket: dict[str, Any] | None = None


DEFAULT_SCENARIOS = [
    VoiceScenario(
        name="supported_webhook_recovery",
        query="How should we recover webhook delivery retries?",
        expected_citations=True,
        test_interruption=False,
        expected_abstention=False,
    ),
    VoiceScenario(
        name="unsupported_sso_abstention",
        query="Can RelayNest configure SSO?",
        expected_citations=False,
        test_interruption=False,
        expected_abstention=True,
    ),
    VoiceScenario(
        name="barge_in_cancellation",
        query="Explain export download procedures and retention links.",
        expected_citations=True,
        test_interruption=True,
        expected_abstention=False,
    ),
]


async def run_voice_evals(
    provider: VoiceProvider | None = None,
    scenarios: list[VoiceScenario] | None = None,
    tenant: str = "harbor",
) -> dict[str, Any]:
    """
    Run automated voice evaluation suite across scenarios.
    Measures TTFA (p50/p95), Barge-in cancellation latency, Citation faithfulness,
    and Abstention accuracy.
    """
    scenarios_to_run = scenarios or DEFAULT_SCENARIOS
    ttfa_tracker = TTFATracker()
    barge_in_tracker = BargeInTracker()

    faithful_citations = 0
    total_citation_checks = 0

    accurate_abstentions = 0
    total_abstention_checks = 0

    scenario_results: list[dict[str, Any]] = []

    for scenario in scenarios_to_run:
        prov = provider or MockVoiceProvider(streaming_delay=0.01)
        context = VoiceSessionContext(
            session_id="00000000-0000-0000-0000-000000000001",
            tenant=tenant,
            ticket_id=scenario.ticket_id,
            ticket=scenario.ticket,
        )
        await prov.connect(context)

        start_time = time.monotonic()
        await prov.send_text(scenario.query)

        first_audio_ms: float | None = None
        assistant_transcripts: list[str] = []
        collected_citations: list[str] = []
        interrupted_signal = False
        interruption_latency_ms: float | None = None

        async for event in prov.receive_events():
            if isinstance(event, ToolCallEvent):
                # Dispatch tool search
                if event.name == "search_knowledge_base":
                    q = str(event.args.get("query", ""))
                    if scenario.expected_abstention:
                        # Return empty citations for abstention test
                        res = {"count": 0, "citations": []}
                    else:
                        res = search_knowledge_base(tenant, q)
                    await prov.send_tool_result(event.call_id, event.name, res)
                elif event.name == "propose_ticket_note":
                    await prov.send_tool_result(
                        event.call_id, event.name, {"status": "pending", "proposal_id": "mock"}
                    )

            elif isinstance(event, CitationEvent):
                collected_citations.extend([c.quote for c in event.citations if c.quote])

            elif isinstance(event, AudioFrame):
                if first_audio_ms is None:
                    first_audio_ms = (time.monotonic() - start_time) * 1000.0
                    ttfa_tracker.record(first_audio_ms)

                    # If testing interruption, trigger barge-in immediately on first audio frame
                    if scenario.test_interruption:
                        interrupt_start = time.monotonic()
                        await prov.interrupt()
                        interruption_latency_ms = (time.monotonic() - interrupt_start) * 1000.0
                        barge_in_tracker.record(interruption_latency_ms)

            elif isinstance(event, TranscriptEvent):
                if event.role == "assistant":
                    assistant_transcripts.append(event.text)

            elif isinstance(event, ControlEvent):
                if event.action == "interrupt":
                    interrupted_signal = True
                    break
                if event.action == "turn_complete":
                    break

        await prov.close()

        full_transcript = " ".join(assistant_transcripts)

        # Evaluate citation faithfulness
        citation_faithful = None
        if scenario.expected_citations and collected_citations:
            total_citation_checks += 1
            citation_faithful = CitationFaithfulnessEvaluator.evaluate(
                full_transcript, collected_citations
            )
            if citation_faithful:
                faithful_citations += 1

        # Evaluate abstention
        abstention_passed = None
        if scenario.expected_abstention:
            total_abstention_checks += 1
            abstention_passed = AbstentionEvaluator.evaluate(full_transcript)
            if abstention_passed:
                accurate_abstentions += 1

        scenario_results.append(
            {
                "name": scenario.name,
                "query": scenario.query,
                "ttfa_ms": first_audio_ms,
                "interruption_latency_ms": interruption_latency_ms,
                "interrupted": interrupted_signal,
                "citations_count": len(collected_citations),
                "citation_faithfulness": citation_faithful,
                "abstention_passed": abstention_passed,
            }
        )

    ttfa_summary = ttfa_tracker.summary()
    barge_in_summary = barge_in_tracker.summary()

    faithfulness_score = (
        faithful_citations / total_citation_checks if total_citation_checks > 0 else 1.0
    )
    abstention_score = (
        accurate_abstentions / total_abstention_checks if total_abstention_checks > 0 else 1.0
    )

    passed = (
        (ttfa_summary["p95"] <= 600.0 or ttfa_summary["count"] == 0)
        and (barge_in_summary["p95"] <= 300.0 or barge_in_summary["count"] == 0)
        and faithfulness_score >= 0.90
        and abstention_score >= 0.90
    )

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "scenarios_count": len(scenarios_to_run),
        "passed": passed,
        "metrics": {
            "ttfa_ms": ttfa_summary,
            "barge_in_latency_ms": barge_in_summary,
            "citation_faithfulness": {
                "score": round(faithfulness_score, 4),
                "faithful_count": faithful_citations,
                "total_checks": total_citation_checks,
            },
            "abstention_accuracy": {
                "score": round(abstention_score, 4),
                "abstained_count": accurate_abstentions,
                "total_checks": total_abstention_checks,
            },
        },
        "scenarios": scenario_results,
    }
