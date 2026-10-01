import io
import math
import struct
import wave
from unittest.mock import patch

import pytest

from evidencedesk.config import settings
from evidencedesk.errors import DomainError
from evidencedesk.voice.recording import TRANSCRIPTION_MODEL, validate_audio


def recording(*, duration=1, silent=False, rate=16000):
    data = io.BytesIO()
    with wave.open(data, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(
            b"".join(
                struct.pack("<h", 0 if silent else int(4000 * math.sin(i / 12)))
                for i in range(int(duration * rate))
            )
        )
    return data.getvalue()


@pytest.mark.parametrize(
    "audio", [b"garbage", recording(duration=31), recording(rate=8000), recording(duration=0.1)]
)
def test_invalid_recording(audio):
    with pytest.raises(DomainError) as exc:
        validate_audio(audio)
    assert exc.value.code == "invalid_audio"


def test_silence_is_rejected():
    with pytest.raises(DomainError) as exc:
        validate_audio(recording(silent=True))
    assert exc.value.code == "no_speech"


def test_transcription_authorization_budget_and_no_persistence(client, owner, monkeypatch):
    monkeypatch.setenv("AI_MODE", "live")
    settings.cache_clear()
    ticket = owner[0]["id"]
    with patch(
        "evidencedesk.voice.recording.CloudflareProvider.call",
        return_value={"text": "What should we do?"},
    ) as call:
        r = client.post(
            f"/tickets/{ticket}/transcribe",
            content=recording(),
            headers={"Content-Type": "audio/wav"},
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"text": "What should we do?", "model": TRANSCRIPTION_MODEL}
        assert call.call_count == 1
        detail = client.get(f"/tickets/{ticket}").json()
        assert detail["runs"] == [] and detail["notes"] == []
        original = client.headers["X-Session-Token"]
        foreign = client.post("/sessions").json()["token"]
        client.headers["X-Session-Token"] = foreign
        assert (
            client.post(
                f"/tickets/{ticket}/transcribe",
                content=recording(),
                headers={"Content-Type": "audio/wav"},
            ).status_code
            == 404
        )
        assert call.call_count == 1
        client.headers["X-Session-Token"] = original
        assert (
            client.post(
                f"/tickets/{ticket}/transcribe",
                content=recording(silent=True),
                headers={"Content-Type": "audio/wav"},
            ).status_code
            == 422
        )
        assert call.call_count == 1
        assert (
            client.post(
                f"/tickets/{ticket}/transcribe",
                content=recording(),
                headers={"Content-Type": "audio/wav"},
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/tickets/{ticket}/transcribe",
                content=recording(),
                headers={"Content-Type": "audio/wav"},
            ).status_code
            == 429
        )
        assert call.call_count == 2


def test_audio_route_size_and_type_boundaries(client, owner):
    ticket = owner[0]["id"]
    assert (
        client.post(
            f"/tickets/{ticket}/transcribe",
            content=b"x" * 960045,
            headers={"Content-Type": "audio/wav"},
        ).status_code
        == 413
    )
    assert (
        client.post(
            f"/tickets/{ticket}/transcribe",
            content=recording(),
            headers={"Content-Type": "audio/webm"},
        ).status_code
        == 415
    )
    assert client.post("/sessions", content=b"x" * 4097).status_code == 413


def test_provider_failure_has_no_fixture_fallback(client, owner, monkeypatch):
    monkeypatch.setenv("AI_MODE", "live")
    settings.cache_clear()
    with patch(
        "evidencedesk.voice.recording.CloudflareProvider.call",
        side_effect=DomainError("provider_unavailable", "Unavailable", 503),
    ):
        r = client.post(
            f"/tickets/{owner[0]['id']}/transcribe",
            content=recording(),
            headers={"Content-Type": "audio/wav"},
        )
        assert r.status_code == 503
        assert "text" not in r.json()


def test_legacy_voice_provider_fails_closed_in_live_mode(monkeypatch):
    from evidencedesk.voice.gateway import get_voice_provider

    monkeypatch.setenv("AI_MODE", "live")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    settings.cache_clear()
    with pytest.raises(DomainError) as exc:
        get_voice_provider()
    assert exc.value.code == "provider_unavailable"
    settings.cache_clear()


def test_legacy_tools_do_not_fabricate_live_results(monkeypatch):
    from evidencedesk.voice.tools import propose_ticket_note, search_knowledge_base

    monkeypatch.setenv("AI_MODE", "live")
    settings.cache_clear()
    with patch(
        "evidencedesk.voice.tools.provider", side_effect=DomainError("provider_quota", "Quota", 429)
    ):
        with pytest.raises(DomainError) as exc:
            search_knowledge_base("tenant", "webhook")
        assert exc.value.code == "provider_quota"
    with patch(
        "evidencedesk.voice.tools.get_ticket",
        side_effect=DomainError("not_found", "Unavailable", 404),
    ):
        with pytest.raises(DomainError) as exc:
            propose_ticket_note({"id": "foreign", "tenant": "tenant"}, "ticket", "Draft")
        assert exc.value.code == "not_found"
    settings.cache_clear()
