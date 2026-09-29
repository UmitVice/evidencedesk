import math
import struct

from pydantic import BaseModel, Field


class VADConfig(BaseModel):
    """Configuration parameters for Voice Activity Detection and frame handling."""

    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    bytes_per_sample: int = Field(default=2, description="Bytes per sample (16-bit PCM = 2)")
    frame_duration_ms: int = Field(default=20, description="Frame duration in milliseconds")
    energy_threshold: float = Field(
        default=0.012, description="Normalized RMS threshold (0.0 - 1.0) for speech detection"
    )
    silence_duration_ms: int = Field(
        default=600, description="Consecutive silence duration in ms to mark end of turn"
    )
    speech_trigger_frames: int = Field(
        default=2, description="Consecutive speech frames required to trigger turn start"
    )
    interruption_frames: int = Field(
        default=3,
        description="Consecutive speech frames during assistant speech to trigger barge-in",
    )

    @property
    def frame_size_bytes(self) -> int:
        samples_per_frame = int(self.sample_rate * (self.frame_duration_ms / 1000.0))
        return samples_per_frame * self.bytes_per_sample


class VADResult(BaseModel):
    """Result of processing an audio frame through VAD."""

    is_speech: bool
    barge_in: bool = False
    end_of_turn: bool = False
    energy: float = 0.0


def calculate_rms(pcm_bytes: bytes) -> float:
    """Calculate normalized RMS energy (0.0 to 1.0) from 16-bit signed integer linear PCM."""
    if len(pcm_bytes) < 2:
        return 0.0
    usable_len = (len(pcm_bytes) // 2) * 2
    if usable_len == 0:
        return 0.0
    samples = struct.unpack(f"<{usable_len // 2}h", pcm_bytes[:usable_len])
    sum_sq = sum(s * s for s in samples)
    return math.sqrt(sum_sq / len(samples)) / 32768.0


class VoiceActivityDetector:
    """
    Detects voice activity, speech completion (end of turn),
    and interruption (barge-in) while assistant audio is streaming.
    """

    def __init__(self, config: VADConfig | None = None) -> None:
        self.config = config or VADConfig()
        self._user_speaking: bool = False
        self._consecutive_speech_frames: int = 0
        self._consecutive_silence_frames: int = 0
        self._assistant_speech_overlap_frames: int = 0

    @property
    def is_user_speaking(self) -> bool:
        return self._user_speaking

    def reset(self) -> None:
        """Reset state tracking for new turn or after interruption."""
        self._user_speaking = False
        self._consecutive_speech_frames = 0
        self._consecutive_silence_frames = 0
        self._assistant_speech_overlap_frames = 0

    def process_frame(self, pcm_bytes: bytes, assistant_speaking: bool = False) -> VADResult:
        """
        Process a single audio frame and evaluate speech, end-of-turn, and barge-in.
        """
        energy = calculate_rms(pcm_bytes)
        is_speech = energy >= self.config.energy_threshold
        barge_in = False
        end_of_turn = False

        if is_speech:
            self._consecutive_speech_frames += 1
            self._consecutive_silence_frames = 0
            if assistant_speaking:
                self._assistant_speech_overlap_frames += 1
                if self._assistant_speech_overlap_frames >= self.config.interruption_frames:
                    barge_in = True
            else:
                self._assistant_speech_overlap_frames = 0

            if (
                not self._user_speaking
                and self._consecutive_speech_frames >= self.config.speech_trigger_frames
            ):
                self._user_speaking = True
        else:
            self._consecutive_speech_frames = 0
            self._assistant_speech_overlap_frames = 0
            if self._user_speaking:
                self._consecutive_silence_frames += 1
                silence_ms = self._consecutive_silence_frames * self.config.frame_duration_ms
                if silence_ms >= self.config.silence_duration_ms:
                    end_of_turn = True
                    self._user_speaking = False
                    self._consecutive_silence_frames = 0

        return VADResult(
            is_speech=is_speech,
            barge_in=barge_in,
            end_of_turn=end_of_turn,
            energy=round(energy, 6),
        )


class AudioFrameBuffer:
    """
    Accumulates arbitrary incoming audio chunks and extracts
    fixed-size frames suitable for VAD and streaming.
    """

    def __init__(self, frame_size: int = 640) -> None:
        self._frame_size = frame_size
        self._buffer = bytearray()

    def push(self, chunk: bytes) -> None:
        """Push arbitrary raw PCM chunk into the buffer."""
        self._buffer.extend(chunk)

    def pop_frame(self) -> bytes | None:
        """Pop a single fixed-size frame from the buffer, or None if insufficient bytes."""
        if len(self._buffer) >= self._frame_size:
            frame = bytes(self._buffer[: self._frame_size])
            del self._buffer[: self._frame_size]
            return frame
        return None

    def pop_all_frames(self) -> list[bytes]:
        """Pop all available fixed-size frames from the buffer."""
        frames: list[bytes] = []
        while len(self._buffer) >= self._frame_size:
            frame = bytes(self._buffer[: self._frame_size])
            del self._buffer[: self._frame_size]
            frames.append(frame)
        return frames

    def get_remaining(self) -> bytes:
        """Return the unconsumed buffer contents."""
        return bytes(self._buffer)

    def clear(self) -> None:
        """Clear all buffered audio bytes."""
        self._buffer.clear()

    @property
    def buffered_bytes(self) -> int:
        """Number of bytes currently in the buffer."""
        return len(self._buffer)
