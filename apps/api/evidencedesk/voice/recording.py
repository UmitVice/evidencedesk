"""Bounded recorded-audio transcription; no sockets or client credentials."""

import base64
import io
import math
import struct
import wave
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from evidencedesk.config import settings
from evidencedesk.errors import DomainError
from evidencedesk.providers import CloudflareProvider
from evidencedesk.quotas import reserve
from evidencedesk.sessions import get_ticket, session

recording_router = APIRouter(tags=["voice"])
Owner = Annotated[dict[str, Any], Depends(session)]
MAX_AUDIO_BYTES = 960044  # 30 seconds, mono PCM16 at 16 kHz plus canonical WAV header.
TRANSCRIPTION_MODEL = "@cf/openai/whisper-large-v3-turbo"


class TranscriptionResponse(BaseModel):
    text: str
    model: str


def validate_audio(audio: bytes) -> None:
    try:
        with wave.open(io.BytesIO(audio), "rb") as wav:
            if (
                wav.getnchannels() != 1
                or wav.getsampwidth() != 2
                or wav.getframerate() != 16000
                or wav.getcomptype() != "NONE"
                or not 4000 <= wav.getnframes() <= 480000
            ):
                raise ValueError("Unsupported audio")
            samples = wav.readframes(wav.getnframes())
            if len(samples) != wav.getnframes() * 2:
                raise ValueError("Truncated audio")
            values = struct.unpack(f"<{len(samples) // 2}h", samples)
            if math.sqrt(sum(x * x for x in values) / len(values)) < 40:
                raise DomainError(
                    "no_speech",
                    "No speech was detected. Record again closer to the microphone.",
                    422,
                )
    except (wave.Error, EOFError, ValueError, struct.error) as exc:
        raise DomainError(
            "invalid_audio", "Record up to 30 seconds of audio and try again.", 422
        ) from exc


def transcribe(owner: dict[str, Any], ticket_id: str, audio: bytes) -> dict[str, str]:
    get_ticket(owner, ticket_id)  # Authorize before quota reservation or provider access.
    validate_audio(audio)
    if settings().ai_mode != "live":
        raise DomainError(
            "provider_unavailable",
            "Voice transcription requires live AI. You can use the sample text instead.",
            503,
        )
    reserve(owner)  # Shared durable environment/session/minute budget, including failed calls.
    result = CloudflareProvider().call(
        TRANSCRIPTION_MODEL,
        {
            "audio": base64.b64encode(audio).decode("ascii"),
            "task": "transcribe",
            "vad_filter": True,
        },
    )
    text = result.get("text")
    if not isinstance(text, str) or not text.strip():
        raise DomainError(
            "no_speech", "No speech was detected. Record again and try speaking clearly.", 422
        )
    if len(text.strip()) > 500:
        raise DomainError(
            "transcript_too_long", "The transcript is too long. Record a shorter question.", 422
        )
    return {"text": text.strip(), "model": TRANSCRIPTION_MODEL}


@recording_router.post("/tickets/{ticket_id}/transcribe", response_model=TranscriptionResponse)
async def transcribe_ticket(ticket_id: UUID, owner: Owner, request: Request):
    if request.headers.get("content-type") != "audio/wav":
        raise DomainError("invalid_audio", "A WAV recording is required.", 415)
    audio = await request.body()
    return await run_in_threadpool(transcribe, owner, str(ticket_id), audio)
