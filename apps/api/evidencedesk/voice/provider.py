from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel, Field

from evidencedesk.voice.protocol import VoiceServerEvent


class VoiceSessionContext(BaseModel):
    """Contextual metadata associated with an active real-time voice session."""

    session_id: str
    tenant: str
    ticket_id: str | None = None
    ticket: dict[str, Any] | None = None
    run_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class VoiceProvider(ABC):
    """
    Abstract Base Class defining the interface for Speech-to-Speech (S2S)
    voice providers (MockVoiceProvider and GeminiLiveProvider).
    """

    @abstractmethod
    async def connect(self, context: VoiceSessionContext) -> None:
        """Initialize provider session and prepare stream."""
        ...

    @abstractmethod
    async def send_audio(self, pcm_bytes: bytes) -> None:
        """Send raw PCM audio bytes to the voice provider."""
        ...

    @abstractmethod
    async def send_text(self, text: str) -> None:
        """Send a text prompt or transcript turn to the voice provider."""
        ...

    @abstractmethod
    async def interrupt(self) -> None:
        """Signal interruption / barge-in to stop active generation."""
        ...

    @abstractmethod
    async def send_tool_result(self, call_id: str, name: str, result: dict[str, Any]) -> None:
        """Send tool execution output back to the voice provider."""
        ...

    @abstractmethod
    def receive_events(self) -> AsyncIterator[VoiceServerEvent]:
        """Stream events (audio frames, transcripts, tool calls, control) from the provider."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close provider connection and release resources."""
        ...
