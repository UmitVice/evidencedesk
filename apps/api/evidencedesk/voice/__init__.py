from evidencedesk.voice.gateway import get_voice_provider, voice_router
from evidencedesk.voice.gemini_live import GeminiLiveProvider
from evidencedesk.voice.mock_provider import MockVoiceProvider, generate_synthetic_pcm
from evidencedesk.voice.protocol import (
    AudioFrame,
    CitationEvent,
    CitationItem,
    ControlAction,
    ControlEvent,
    ToolCallEvent,
    ToolResultEvent,
    TranscriptEvent,
    VoiceClientEvent,
    VoiceServerEvent,
    parse_client_message,
    serialize_client_message,
    serialize_server_message,
)
from evidencedesk.voice.provider import VoiceProvider, VoiceSessionContext
from evidencedesk.voice.tools import TOOL_DECLARATIONS, propose_ticket_note, search_knowledge_base
from evidencedesk.voice.vad import (
    AudioFrameBuffer,
    VADConfig,
    VADResult,
    VoiceActivityDetector,
    calculate_rms,
)

__all__ = [
    "AudioFrame",
    "AudioFrameBuffer",
    "CitationEvent",
    "CitationItem",
    "ControlAction",
    "ControlEvent",
    "GeminiLiveProvider",
    "MockVoiceProvider",
    "ToolCallEvent",
    "ToolResultEvent",
    "TranscriptEvent",
    "VADConfig",
    "VADResult",
    "VoiceActivityDetector",
    "VoiceClientEvent",
    "VoiceProvider",
    "VoiceServerEvent",
    "VoiceSessionContext",
    "calculate_rms",
    "generate_synthetic_pcm",
    "get_voice_provider",
    "parse_client_message",
    "propose_ticket_note",
    "search_knowledge_base",
    "serialize_client_message",
    "serialize_server_message",
    "TOOL_DECLARATIONS",
    "voice_router",
]
