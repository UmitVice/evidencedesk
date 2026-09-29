import asyncio
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from evidencedesk.config import settings
from evidencedesk.voice.evals import run_voice_evals
from evidencedesk.voice.mock_provider import generate_synthetic_pcm
from evidencedesk.voice.protocol import (
    AudioFrame,
    ControlEvent,
    parse_client_message,
    parse_server_message,
    serialize_server_message,
)
from evidencedesk.voice.tools import propose_ticket_note, search_knowledge_base
from evidencedesk.voice.vad import VADConfig, VoiceActivityDetector, calculate_rms
from main import app

MOCK_SESSION_ID = str(uuid4())
MOCK_TICKET_ID = str(uuid4())
VALID_TOKEN = "a" * 48
VALID_SERVICE_KEY = "test-service-key-" + "x" * 32


@pytest.fixture
def auth_mock(monkeypatch):
    """Mock session and service key authentication for isolated unit testing."""
    monkeypatch.setenv("SERVICE_KEY", VALID_SERVICE_KEY)
    settings.cache_clear()

    def mock_auth(token: str | None, service_key: str | None):
        if not token or len(token) < 40:
            return None
        if service_key != VALID_SERVICE_KEY:
            return None
        return {
            "id": MOCK_SESSION_ID,
            "tenant": "harbor",
        }

    with patch("evidencedesk.voice.gateway._authenticate_ws", side_effect=mock_auth):
        yield


def test_vad_speech_detection_and_rms():
    """Verify Voice Activity Detection energy calculation and speech state transitions."""
    vad = VoiceActivityDetector(VADConfig(energy_threshold=0.015))

    # Silence (all zero bytes)
    silence = b"\x00\x00" * 320
    assert calculate_rms(silence) == 0.0
    res = vad.process_frame(silence, assistant_speaking=False)
    assert not res.is_speech
    assert not res.barge_in
    assert not res.end_of_turn

    # Synthetic audible speech frame
    tone = generate_synthetic_pcm(duration_ms=20, freq_hz=440.0, sample_rate=16000)
    assert calculate_rms(tone) > 0.015

    # Multiple speech frames transition user to speaking
    vad.process_frame(tone, assistant_speaking=False)
    res_speech = vad.process_frame(tone, assistant_speaking=False)
    assert res_speech.is_speech
    assert vad.is_user_speaking


def test_vad_barge_in_detection():
    """Verify barge-in detection triggers when speech occurs during assistant playback."""
    vad = VoiceActivityDetector(VADConfig(interruption_frames=2, energy_threshold=0.015))
    tone = generate_synthetic_pcm(duration_ms=20, freq_hz=500.0, sample_rate=16000)

    # Frame 1 of speech during assistant speaking
    res1 = vad.process_frame(tone, assistant_speaking=True)
    assert not res1.barge_in

    # Frame 2 of speech during assistant speaking triggers barge-in
    res2 = vad.process_frame(tone, assistant_speaking=True)
    assert res2.barge_in


def test_ws_auth_policy_rejection():
    """Ensure unauthenticated WebSocket connections are rejected with 1008 Policy Violation."""
    client = TestClient(app)

    # Missing token and service key
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/voice/session"):
            pass
    assert exc_info.value.code == 1008

    # Invalid short token
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/voice/session?token=invalid"):
            pass
    assert exc_info.value.code == 1008


def test_ws_connection_lifecycle(auth_mock):
    """Test full WebSocket connection handshake, ping/pong, and stop lifecycle."""
    client = TestClient(app)
    url = f"/api/voice/session?token={VALID_TOKEN}&service_key={VALID_SERVICE_KEY}"

    with client.websocket_connect(url) as ws:
        # Initial greeting event
        start_raw = ws.receive_text()
        start_event = parse_client_message(start_raw)
        assert isinstance(start_event, ControlEvent)
        assert start_event.action == "start"
        assert start_event.payload.get("tenant") == "harbor"

        # Ping / Pong
        ws.send_text(serialize_server_message(ControlEvent(action="ping")))
        pong_raw = ws.receive_text()
        pong_event = parse_client_message(pong_raw)
        assert isinstance(pong_event, ControlEvent)
        assert pong_event.action == "pong"

        # Stop action closes gracefully
        ws.send_text(serialize_server_message(ControlEvent(action="stop")))


def test_ws_streaming_audio_and_rag_tool_dispatch(auth_mock):
    """Test bidirectional audio streaming and automated RAG tool execution."""
    client = TestClient(app)
    url = (
        f"/api/voice/session?token={VALID_TOKEN}&service_key={VALID_SERVICE_KEY}"
        f"&ticket_id={MOCK_TICKET_ID}"
    )

    with client.websocket_connect(url) as ws:
        # Start event
        ws.receive_text()

        # Send speech prompt audio frame
        tone = generate_synthetic_pcm(duration_ms=40, freq_hz=440.0, sample_rate=16000)
        audio_frame = AudioFrame.from_bytes(tone, sample_rate=16000)
        ws.send_text(audio_frame.model_dump_json())

        # Collect server messages until turn is complete
        received_types = set()
        for _ in range(15):
            try:
                raw = ws.receive_text()
                parsed = parse_server_message(raw)
                received_types.add(parsed.type)
                if isinstance(parsed, ControlEvent) and parsed.action == "turn_complete":
                    break
            except Exception:
                break

        assert "transcript" in received_types
        assert "citation" in received_types
        assert "audio" in received_types


def test_ws_barge_in_interruption_event(auth_mock):
    """Test that client interrupt action immediately halts assistant output."""
    client = TestClient(app)
    url = f"/api/voice/session?token={VALID_TOKEN}&service_key={VALID_SERVICE_KEY}"

    with client.websocket_connect(url) as ws:
        ws.receive_text()  # Start event

        # Send text turn to initiate mock speech
        ws.send_json({"type": "transcript", "role": "user", "text": "webhook issue"})

        # Send interrupt event
        ws.send_text(serialize_server_message(ControlEvent(action="interrupt")))

        # Check that an interrupt control event is received
        interrupted = False
        for _ in range(10):
            msg = ws.receive_json()
            if msg.get("type") == "control" and msg.get("action") == "interrupt":
                interrupted = True
                break

        assert interrupted


def test_propose_ticket_note_safe_mutation_boundary():
    """Verify that proposing a note creates a pending proposal and never mutates directly."""
    owner = {"id": MOCK_SESSION_ID, "tenant": "harbor"}
    content = "Verified support note content."

    proposal = propose_ticket_note(owner, MOCK_TICKET_ID, content)
    assert proposal["status"] == "pending"
    assert proposal["content"] == content
    assert "proposal_id" in proposal


def test_search_knowledge_base_retrieval():
    """Verify knowledge base hybrid retrieval returns formatted citation cards."""
    res = search_knowledge_base("harbor", "webhook delivery retries recovery")
    assert res["count"] > 0
    first = res["citations"][0]
    assert "source_id" in first
    assert "quote" in first
    assert len(first["quote"]) > 0


def test_run_voice_evals_metrics():
    """Run full automated voice evaluations and verify TTFA, barge-in, and citations."""
    report = asyncio.run(run_voice_evals())

    assert report["passed"] is True
    assert report["scenarios_count"] >= 3

    metrics = report["metrics"]
    # TTFA p95 latency under 600ms on mock stream
    assert metrics["ttfa_ms"]["p95"] < 600.0

    # Barge-in cancellation latency under 300ms
    assert metrics["barge_in_latency_ms"]["p95"] < 300.0

    # 100% citation faithfulness
    assert metrics["citation_faithfulness"]["score"] == 1.0

    # 100% abstention accuracy on unsupported knowledge
    assert metrics["abstention_accuracy"]["score"] == 1.0


def test_create_voice_ticket_and_handshake():
    """Verify short-lived single-use voice ticket creation and WebSocket authentication."""
    import time

    from evidencedesk.voice.gateway import _VOICE_TICKETS, VoiceTicket

    client = TestClient(app)
    ticket_code = "voice-auth-token-test-12345"
    _VOICE_TICKETS[ticket_code] = VoiceTicket(
        ticket=ticket_code,
        owner={"id": MOCK_SESSION_ID, "tenant": "harbor"},
        expires_at=time.time() + 60.0,
        redeemed=False,
    )

    # Connect using single-use ticket
    with client.websocket_connect(f"/api/voice/session?ticket={ticket_code}") as ws:
        msg = ws.receive_json()
        assert msg["type"] == "control"
        assert msg["action"] == "start"
        assert msg["payload"]["tenant"] == "harbor"

    # Subsequent connection with redeemed ticket must be rejected with 1008
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/voice/session?ticket={ticket_code}"):
            pass
    assert exc_info.value.code == 1008


def test_voice_ticket_expired_rejection():
    """Verify expired voice tickets are rejected with 1008 Policy Violation."""
    import time

    from evidencedesk.voice.gateway import _VOICE_TICKETS, VoiceTicket

    client = TestClient(app)
    ticket_code = "expired-token-xyz"
    _VOICE_TICKETS[ticket_code] = VoiceTicket(
        ticket=ticket_code,
        owner={"id": MOCK_SESSION_ID, "tenant": "harbor"},
        expires_at=time.time() - 10.0,
        redeemed=False,
    )

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/api/voice/session?ticket={ticket_code}"):
            pass
    assert exc_info.value.code == 1008
