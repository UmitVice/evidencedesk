import asyncio
import hashlib
import logging
import secrets
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from evidencedesk.config import settings
from evidencedesk.db import connection
from evidencedesk.sessions import get_ticket
from evidencedesk.voice.gemini_live import GeminiLiveProvider
from evidencedesk.voice.mock_provider import MockVoiceProvider
from evidencedesk.voice.protocol import (
    AudioFrame,
    CitationEvent,
    CitationItem,
    ControlEvent,
    ToolCallEvent,
    ToolResultEvent,
    TranscriptEvent,
    parse_client_message,
    serialize_server_message,
)
from evidencedesk.voice.provider import VoiceProvider, VoiceSessionContext
from evidencedesk.voice.tools import propose_ticket_note, search_knowledge_base
from evidencedesk.voice.vad import AudioFrameBuffer, VADConfig, VoiceActivityDetector

logger = logging.getLogger("evidencedesk.voice.gateway")

voice_router = APIRouter(prefix="/api/voice", tags=["voice"])


def _authenticate_ws(
    session_token: str | None,
    service_key: str | None,
) -> dict[str, Any] | None:
    """Validate service key and session token for WebSocket connections."""
    config = settings()
    expected_service_key = config.service_key.get_secret_value()
    if len(expected_service_key) >= 32:
        if not service_key or not secrets.compare_digest(service_key, expected_service_key):
            return None

    if not session_token or not (40 <= len(session_token) <= 128):
        return None

    digest = hashlib.sha256(session_token.encode()).hexdigest()
    with connection() as conn:
        row = conn.execute(
            "SELECT id,tenant,expires_at FROM evidence.sessions "
            "WHERE token_hash=%s AND expires_at > now()",
            (digest,),
        ).fetchone()

    return row


def get_voice_provider(provider_name: str | None = None) -> VoiceProvider:
    """Factory selecting GeminiLiveProvider or MockVoiceProvider based on configuration."""
    config = settings()
    if provider_name == "gemini" or (
        provider_name is None
        and config.ai_mode == "live"
        and bool(config.gemini_api_key.get_secret_value())
    ):
        return GeminiLiveProvider()
    return MockVoiceProvider()


@voice_router.websocket("/session")
async def voice_session_endpoint(
    websocket: WebSocket,
    token: str | None = Query(None),
    service_key: str | None = Query(None),
    ticket_id: str | None = Query(None),
    provider_name: str | None = Query(None, alias="provider"),
) -> None:
    """
    Bidirectional WebSocket gateway for real-time speech copilot sessions.
    Validates tenant and session credentials, coordinates VAD, dispatches RAG tools,
    and streams synthesized audio and citation cards.
    """
    # Fallback to headers if query parameters are omitted
    effective_token = token or websocket.headers.get("x-session-token")
    effective_service_key = service_key or websocket.headers.get("x-service-key")

    owner = _authenticate_ws(effective_token, effective_service_key)
    if owner is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    ticket: dict[str, Any] | None = None
    if ticket_id:
        try:
            ticket = get_ticket(owner, ticket_id)
        except Exception:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await websocket.accept()

    # Create session context and initialize provider
    context = VoiceSessionContext(
        session_id=str(owner["id"]),
        tenant=owner["tenant"],
        ticket_id=ticket_id,
        ticket=ticket,
    )
    provider = get_voice_provider(provider_name)
    vad = VoiceActivityDetector(VADConfig())
    frame_buffer = AudioFrameBuffer(frame_size=vad.config.frame_size_bytes)

    try:
        await provider.connect(context)
    except Exception as exc:
        logger.error(f"Failed to connect voice provider: {exc}")
        await websocket.send_text(
            serialize_server_message(
                ControlEvent(action="error", message=f"Failed to connect voice provider: {exc}")
            )
        )
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    # Notify client that voice session is ready
    await websocket.send_text(
        serialize_server_message(
            ControlEvent(
                action="start",
                message="Voice session established",
                payload={
                    "session_id": str(owner["id"]),
                    "tenant": owner["tenant"],
                    "ticket_id": ticket_id,
                    "mode": settings().ai_mode,
                },
            )
        )
    )

    is_assistant_speaking = False

    async def client_to_provider() -> None:
        nonlocal is_assistant_speaking
        try:
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    break

                raw_bytes = message.get("bytes")
                raw_text = message.get("text")

                if raw_bytes is not None:
                    event = parse_client_message(raw_bytes)
                elif raw_text is not None:
                    event = parse_client_message(raw_text)
                else:
                    continue

                if isinstance(event, AudioFrame):
                    pcm = event.to_bytes()
                    frame_buffer.push(pcm)
                    for frame in frame_buffer.pop_all_frames():
                        vad_res = vad.process_frame(
                            frame, assistant_speaking=is_assistant_speaking
                        )
                        if vad_res.barge_in:
                            is_assistant_speaking = False
                            await provider.interrupt()
                            await websocket.send_text(
                                serialize_server_message(
                                    ControlEvent(
                                        action="interrupt",
                                        message="Interrupted by user speech",
                                    )
                                )
                            )
                        await provider.send_audio(frame)

                elif isinstance(event, ControlEvent):
                    if event.action == "interrupt":
                        is_assistant_speaking = False
                        await provider.interrupt()
                    elif event.action == "ping":
                        await websocket.send_text(
                            serialize_server_message(ControlEvent(action="pong"))
                        )
                    elif event.action == "stop":
                        break

                elif isinstance(event, TranscriptEvent):
                    await provider.send_text(event.text)

                elif isinstance(event, ToolResultEvent):
                    await provider.send_tool_result(event.call_id, event.name, event.result)

        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception as exc:
            logger.warning(f"Error in client_to_provider stream: {exc}")

    async def provider_to_client() -> None:
        nonlocal is_assistant_speaking
        try:
            async for event in provider.receive_events():
                if isinstance(event, AudioFrame):
                    is_assistant_speaking = True
                    await websocket.send_text(serialize_server_message(event))

                elif isinstance(event, ToolCallEvent):
                    if event.name == "search_knowledge_base":
                        query = str(event.args.get("query", ""))
                        tool_res = search_knowledge_base(owner["tenant"], query)
                        citations = [
                            CitationItem(**item) for item in tool_res.get("citations", [])
                        ]
                        # Immediate citation card event for UI
                        await websocket.send_text(
                            serialize_server_message(CitationEvent(citations=citations))
                        )
                        # Notify client of tool execution
                        await websocket.send_text(
                            serialize_server_message(
                                ToolResultEvent(
                                    call_id=event.call_id,
                                    name=event.name,
                                    result=tool_res,
                                )
                            )
                        )
                        # Return output to provider
                        await provider.send_tool_result(event.call_id, event.name, tool_res)

                    elif event.name == "propose_ticket_note":
                        content = str(event.args.get("content", ""))
                        if ticket_id:
                            tool_res = propose_ticket_note(owner, ticket_id, content)
                        else:
                            tool_res = {"error": "Active ticket required to propose note."}

                        await websocket.send_text(
                            serialize_server_message(
                                ToolResultEvent(
                                    call_id=event.call_id,
                                    name=event.name,
                                    result=tool_res,
                                )
                            )
                        )
                        await provider.send_tool_result(event.call_id, event.name, tool_res)

                    else:
                        tool_res = {"error": f"Unknown tool: {event.name}"}
                        await provider.send_tool_result(event.call_id, event.name, tool_res)

                elif isinstance(event, ControlEvent):
                    if event.action in ("turn_complete", "interrupt"):
                        is_assistant_speaking = False
                    await websocket.send_text(serialize_server_message(event))

                else:
                    await websocket.send_text(serialize_server_message(event))

        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception as exc:
            logger.warning(f"Error in provider_to_client stream: {exc}")

    reader_task = asyncio.create_task(client_to_provider())
    writer_task = asyncio.create_task(provider_to_client())

    try:
        # Wait until either reader or writer finishes
        done, pending = await asyncio.wait(
            [reader_task, writer_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    finally:
        await provider.close()
        try:
            await websocket.close()
        except Exception:
            pass
