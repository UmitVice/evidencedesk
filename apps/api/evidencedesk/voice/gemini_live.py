import asyncio
import base64
import json
import logging
import os
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import websockets
from websockets.asyncio.client import ClientConnection

from evidencedesk.config import settings
from evidencedesk.errors import DomainError
from evidencedesk.voice.protocol import (
    AudioFrame,
    ControlEvent,
    ToolCallEvent,
    TranscriptEvent,
    VoiceServerEvent,
)
from evidencedesk.voice.provider import VoiceProvider, VoiceSessionContext
from evidencedesk.voice.tools import TOOL_DECLARATIONS

logger = logging.getLogger("evidencedesk.voice.gemini")

GEMINI_LIVE_URL = (
    "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1alpha"
    ".GenerativeService.BidiGenerateContent"
)
GEMINI_MODEL = "models/gemini-2.0-flash-exp"

GEMINI_SYSTEM_PROMPT = (
    "You are the EvidenceDesk Voice Copilot, a real-time support copilot for SaaS ticket "
    "resolution.\nStrict rules:\n"
    "1. Speak concisely in natural conversational English. Keep spoken replies under 3 sentences.\n"
    "2. Rely strictly on retrieved knowledge from search_knowledge_base. "
    "Never fabricate policies or procedures.\n"
    "3. When helpful, propose an internal note using propose_ticket_note for agent review.\n"
    "4. You cannot execute mutations or close tickets directly. "
    "Proposals remain pending for human approval.\n"
    "5. If evidence is insufficient, clearly state that the policy is unverified or unresolved."
)


class GeminiLiveProvider(VoiceProvider):
    """
    Real GCP / Gemini 2.0 Multimodal Live API WebSocket client using standard asyncio websockets.
    Connects to the bidirectional streaming endpoint when GEMINI_API_KEY is supplied.
    """

    def __init__(self, api_key: str | None = None, model: str = GEMINI_MODEL) -> None:
        self.api_key = (
            api_key
            or settings().gemini_api_key.get_secret_value()
            or os.getenv("GEMINI_API_KEY", "")
        )
        self.model = model
        self._ws: ClientConnection | None = None
        self._context: VoiceSessionContext | None = None
        self._event_queue: asyncio.Queue[VoiceServerEvent | None] = asyncio.Queue()
        self._read_task: asyncio.Task[None] | None = None
        self._closed: bool = False

    async def connect(self, context: VoiceSessionContext) -> None:
        if not self.api_key:
            raise DomainError(
                "provider_unavailable",
                "Gemini Live API key is not configured.",
                503,
            )

        self._context = context
        self._closed = False
        url = f"{GEMINI_LIVE_URL}?key={self.api_key}"

        try:
            self._ws = await websockets.connect(url)
            await self._send_setup_message()
            self._read_task = asyncio.create_task(self._read_loop())
        except Exception as exc:
            logger.error(f"Failed to connect to Gemini Live API: {exc}")
            raise DomainError(
                "provider_transient",
                f"Gemini Live connection failed: {exc}",
                503,
            ) from exc

    async def _send_setup_message(self) -> None:
        assert self._ws is not None
        ticket_context = ""
        if self._context and self._context.ticket:
            ticket = self._context.ticket
            title = ticket.get("title", "")
            body = ticket.get("body", "")
            ticket_context = f"\nCurrent Ticket Context:\nTitle: {title}\nBody: {body}"

        setup_msg = {
            "setup": {
                "model": self.model,
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": "Puck"
                            }
                        }
                    },
                },
                "systemInstruction": {
                    "parts": [{"text": GEMINI_SYSTEM_PROMPT + ticket_context}]
                },
                "tools": [
                    {
                        "functionDeclarations": TOOL_DECLARATIONS
                    }
                ],
            }
        }
        await self._ws.send(json.dumps(setup_msg))

    async def send_audio(self, pcm_bytes: bytes) -> None:
        if not self._ws or self._closed:
            return
        b64_audio = base64.b64encode(pcm_bytes).decode("ascii")
        msg = {
            "realtimeInput": {
                "mediaChunks": [
                    {
                        "mimeType": "audio/pcm;rate=16000",
                        "data": b64_audio,
                    }
                ]
            }
        }
        try:
            await self._ws.send(json.dumps(msg))
        except Exception as exc:
            logger.warning(f"Error sending audio to Gemini: {exc}")

    async def send_text(self, text: str) -> None:
        if not self._ws or self._closed:
            return
        msg = {
            "clientContent": {
                "turns": [
                    {
                        "role": "user",
                        "parts": [{"text": text}],
                    }
                ],
                "turnComplete": True,
            }
        }
        try:
            await self._ws.send(json.dumps(msg))
        except Exception as exc:
            logger.warning(f"Error sending text to Gemini: {exc}")

    async def interrupt(self) -> None:
        """Interrupt active Gemini generation."""
        if not self._ws or self._closed:
            return
        # Signal interruption to client/stream queue
        await self._event_queue.put(
            ControlEvent(action="interrupt", message="Turn interrupted by user speech")
        )

    async def send_tool_result(self, call_id: str, name: str, result: dict[str, Any]) -> None:
        if not self._ws or self._closed:
            return
        msg = {
            "toolResponse": {
                "functionResponses": [
                    {
                        "response": {"output": result},
                        "id": call_id,
                    }
                ]
            }
        }
        try:
            await self._ws.send(json.dumps(msg))
        except Exception as exc:
            logger.warning(f"Error sending tool result to Gemini: {exc}")

    async def receive_events(self) -> AsyncIterator[VoiceServerEvent]:
        while not self._closed:
            try:
                event = await self._event_queue.get()
                if event is None:
                    break
                yield event
            except asyncio.CancelledError:
                break

    async def _read_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                if self._closed:
                    break
                payload = json.loads(raw)

                # Check serverContent
                if "serverContent" in payload:
                    sc = payload["serverContent"]
                    if "modelTurn" in sc:
                        for part in sc["modelTurn"].get("parts", []):
                            if "text" in part:
                                await self._event_queue.put(
                                    TranscriptEvent(role="model", text=part["text"], is_final=False)
                                )
                            if "inlineData" in part:
                                data = part["inlineData"].get("data", "")
                                if data:
                                    await self._event_queue.put(
                                        AudioFrame(data=data, sample_rate=24000)
                                    )
                    if sc.get("interrupted"):
                        await self._event_queue.put(
                            ControlEvent(action="interrupt", message="Interrupted by model")
                        )
                    if sc.get("turnComplete"):
                        await self._event_queue.put(
                            ControlEvent(action="turn_complete")
                        )

                # Check toolCall
                if "toolCall" in payload:
                    for call in payload["toolCall"].get("functionCalls", []):
                        call_id = call.get("id") or f"call-{uuid4().hex[:8]}"
                        await self._event_queue.put(
                            ToolCallEvent(
                                call_id=call_id,
                                name=call.get("name", ""),
                                args=call.get("args", {}),
                            )
                        )
        except websockets.ConnectionClosed:
            pass
        except Exception as exc:
            logger.error(f"Error in Gemini Live read loop: {exc}")
        finally:
            await self._event_queue.put(None)

    async def close(self) -> None:
        self._closed = True
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
        await self._event_queue.put(None)
