import asyncio
import math
import struct
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from evidencedesk.voice.protocol import (
    AudioFrame,
    CitationEvent,
    CitationItem,
    ControlEvent,
    ToolCallEvent,
    TranscriptEvent,
    VoiceServerEvent,
)
from evidencedesk.voice.provider import VoiceProvider, VoiceSessionContext


def generate_synthetic_pcm(
    duration_ms: int = 100, freq_hz: float = 440.0, sample_rate: int = 24000
) -> bytes:
    """Generate deterministic synthetic 16-bit linear PCM audio sine wave."""
    num_samples = int(sample_rate * (duration_ms / 1000.0))
    raw = bytearray()
    for i in range(num_samples):
        val = int(math.sin(2 * math.pi * freq_hz * (i / sample_rate)) * 3600)
        raw.extend(struct.pack("<h", val))
    return bytes(raw)


class MockVoiceProvider(VoiceProvider):
    """
    Deterministic offline mock voice provider.
    Produces synthetic audio chunks, triggers tool-calling RAG flows,
    and handles barge-in interruptions without external cloud billing.
    """

    def __init__(self, streaming_delay: float = 0.0) -> None:
        self.streaming_delay = streaming_delay
        self._context: VoiceSessionContext | None = None
        self._event_queue: asyncio.Queue[VoiceServerEvent | None] = asyncio.Queue()
        self._pending_tool_futures: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._interrupted: bool = False
        self._closed: bool = False
        self._active_turn_task: asyncio.Task[None] | None = None
        self._turn_completed: bool = False

    async def connect(self, context: VoiceSessionContext) -> None:
        self._context = context
        self._interrupted = False
        self._closed = False
        self._turn_completed = False

    async def send_audio(self, pcm_bytes: bytes) -> None:
        """Handle incoming user audio. In mock mode, triggers response once per speech turn."""
        if self._closed or self._interrupted or self._turn_completed:
            return
        # If no turn is running and current turn not completed, initiate simulated response
        if self._active_turn_task is None or self._active_turn_task.done():
            ticket_sample = (
                self._context.ticket.get("sample", "webhook")
                if self._context and self._context.ticket
                else "webhook"
            )
            prompt = f"How should we handle {ticket_sample} issue?"
            self._active_turn_task = asyncio.create_task(self._simulate_turn(prompt))

    async def send_text(self, text: str) -> None:
        """Handle incoming text prompt from user."""
        if self._closed:
            return
        if self._active_turn_task and not self._active_turn_task.done():
            self._active_turn_task.cancel()
        self._interrupted = False
        self._turn_completed = False
        self._active_turn_task = asyncio.create_task(self._simulate_turn(text))

    async def interrupt(self) -> None:
        """Handle barge-in interruption immediately."""
        self._interrupted = True
        self._turn_completed = False
        if self._active_turn_task and not self._active_turn_task.done():
            self._active_turn_task.cancel()

        # Cancel pending tool futures
        for fut in self._pending_tool_futures.values():
            if not fut.done():
                fut.cancel()
        self._pending_tool_futures.clear()

        # Drain audio from queue to silence output
        drained: list[VoiceServerEvent | None] = []
        while not self._event_queue.empty():
            try:
                item = self._event_queue.get_nowait()
                if item and item.type != "audio":
                    drained.append(item)
            except asyncio.QueueEmpty:
                break

        for item in drained:
            await self._event_queue.put(item)

        await self._event_queue.put(
            ControlEvent(action="interrupt", message="Playback interrupted by user speech")
        )

    async def send_tool_result(self, call_id: str, name: str, result: dict[str, Any]) -> None:
        """Receive tool result and resolve waiting future."""
        fut = self._pending_tool_futures.pop(call_id, None)
        if fut and not fut.done():
            fut.set_result(result)

    async def receive_events(self) -> AsyncIterator[VoiceServerEvent]:
        """Stream generated voice events to the gateway."""
        while not self._closed:
            try:
                event = await self._event_queue.get()
                if event is None:
                    break
                yield event
            except asyncio.CancelledError:
                break

    async def close(self) -> None:
        """Clean up background tasks and release resources."""
        self._closed = True
        if self._active_turn_task and not self._active_turn_task.done():
            self._active_turn_task.cancel()
        for fut in self._pending_tool_futures.values():
            if not fut.done():
                fut.cancel()
        self._pending_tool_futures.clear()
        await self._event_queue.put(None)

    async def _simulate_turn(self, query: str) -> None:
        """Simulate a complete turn: user transcript -> tool call -> citations -> response audio."""
        try:
            self._interrupted = False
            # 1. User Transcript
            await self._event_queue.put(
                TranscriptEvent(role="user", text=query, is_final=True)
            )

            # 2. Tool Call: search_knowledge_base
            call_id = f"call-{uuid4().hex[:8]}"
            fut: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
            self._pending_tool_futures[call_id] = fut

            await self._event_queue.put(
                ToolCallEvent(
                    call_id=call_id,
                    name="search_knowledge_base",
                    args={"query": query},
                )
            )

            # Wait for gateway to execute tool and return result
            try:
                tool_result = await asyncio.wait_for(fut, timeout=5.0)
            except (TimeoutError, asyncio.CancelledError):
                if self._interrupted:
                    return
                tool_result = {"count": 0, "citations": []}

            if self._interrupted:
                return

            # 3. Emit Citations
            citations = [
                CitationItem(**item) for item in tool_result.get("citations", [])
            ]
            if citations:
                await self._event_queue.put(CitationEvent(citations=citations))

            # 4. Optional Tool Call: propose_ticket_note if ticket exists
            if self._context and self._context.ticket_id and citations:
                note_call_id = f"call-note-{uuid4().hex[:8]}"
                note_fut: asyncio.Future[dict[str, Any]] = (
                    asyncio.get_running_loop().create_future()
                )
                self._pending_tool_futures[note_call_id] = note_fut

                first_quote = citations[0].quote
                draft_content = f"Guidance verified: {first_quote}"
                await self._event_queue.put(
                    ToolCallEvent(
                        call_id=note_call_id,
                        name="propose_ticket_note",
                        args={"content": draft_content},
                    )
                )
                try:
                    await asyncio.wait_for(note_fut, timeout=5.0)
                except (TimeoutError, asyncio.CancelledError):
                    if self._interrupted:
                        return

            if self._interrupted:
                return

            # 5. Assistant Spoken Response & Audio Frames
            if citations:
                response_text = (
                    f"Based on the knowledge base documentation: {citations[0].quote} "
                    "I have drafted a note for your review."
                )
            else:
                response_text = (
                    "I checked the documentation, but could not find matching evidence "
                    "for this request."
                )

            # Assistant Transcript Header
            await self._event_queue.put(
                TranscriptEvent(role="assistant", text=response_text, is_final=False)
            )

            # Synthetic Audio Chunks (24kHz PCM)
            synthetic_pcm = generate_synthetic_pcm(
                duration_ms=100, freq_hz=440.0, sample_rate=24000
            )
            for _ in range(2):
                if self._interrupted:
                    return
                frame = AudioFrame.from_bytes(synthetic_pcm, sample_rate=24000)
                await self._event_queue.put(frame)
                if self.streaming_delay > 0:
                    await asyncio.sleep(self.streaming_delay)

            # Final Transcript and Turn Complete
            if not self._interrupted:
                self._turn_completed = True
                await self._event_queue.put(
                    TranscriptEvent(role="assistant", text=response_text, is_final=True)
                )
                await self._event_queue.put(ControlEvent(action="turn_complete"))

        except asyncio.CancelledError:
            pass
