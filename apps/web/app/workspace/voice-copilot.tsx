"use client";

import { useEffect, useRef, useState } from "react";

// Produce a bounded, portable PCM WAV for the server-side speech recognizer.
async function wavRecording(blob: Blob): Promise<Blob> {
  const context = new AudioContext();
  try {
    const audio = await context.decodeAudioData(await blob.arrayBuffer());
    if (audio.duration > 30.5)
      throw new Error("Record up to 30 seconds and try again.");
    const count = Math.min(480000, Math.floor(audio.duration * 16000));
    const buffer = new ArrayBuffer(44 + count * 2);
    const view = new DataView(buffer);
    const text = (offset: number, value: string) => {
      for (let i = 0; i < value.length; i++)
        view.setUint8(offset + i, value.charCodeAt(i));
    };
    text(0, "RIFF");
    view.setUint32(4, 36 + count * 2, true);
    text(8, "WAVE");
    text(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, 16000, true);
    view.setUint32(28, 32000, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    text(36, "data");
    view.setUint32(40, count * 2, true);
    const channels = Array.from({ length: audio.numberOfChannels }, (_, i) =>
      audio.getChannelData(i),
    );
    for (let i = 0; i < count; i++) {
      const position = (i * audio.sampleRate) / 16000;
      const left = Math.floor(position),
        fraction = position - left;
      const value =
        channels.reduce(
          (sum, channel) =>
            sum +
            channel[left] * (1 - fraction) +
            (channel[Math.min(left + 1, channel.length - 1)] ?? 0) * fraction,
          0,
        ) / channels.length;
      const sample = Math.max(-1, Math.min(1, value));
      view.setInt16(44 + i * 2, sample * (sample < 0 ? 32768 : 32767), true);
    }
    return new Blob([buffer], { type: "audio/wav" });
  } finally {
    await context.close();
  }
}

export function VoiceCopilot({
  ticketId,
  ticketTitle,
  busy,
  onAnalyze,
  onBusyChange,
}: {
  ticketId: string;
  ticketTitle: string;
  busy: boolean;
  onAnalyze: (text: string) => Promise<void>;
  onBusyChange: (busy: boolean) => void;
}) {
  const [state, setState] = useState<
    "idle" | "accessing" | "recording" | "transcribing"
  >("idle");
  const [error, setError] = useState<string | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [transcript, setTranscript] = useState("");
  const [seconds, setSeconds] = useState(0);
  const [retryAvailable, setRetryAvailable] = useState(false);
  const stream = useRef<MediaStream | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const url = useRef<string | null>(null);
  const pendingAudio = useRef<Blob | null>(null);
  const request = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const starting = useRef(false);

  useEffect(() => {
    onBusyChange(state !== "idle");
    return () => onBusyChange(false);
  }, [state, onBusyChange]);

  function releaseMicrophone() {
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
  }
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      request.current?.abort();
      if (recorder.current) {
        recorder.current.onstop = null;
        if (recorder.current.state !== "inactive") recorder.current.stop();
      }
      releaseMicrophone();
      if (url.current) URL.revokeObjectURL(url.current);
    };
  }, []);

  async function transcribe(blob: Blob) {
    setState("transcribing");
    setError(null);
    const controller = new AbortController();
    request.current = controller;
    const timeout = setTimeout(() => controller.abort(), 45000);
    try {
      const wav = await wavRecording(blob);
      if (!mounted.current) return;
      const response = await fetch(`/api/tickets/${ticketId}/transcribe`, {
        method: "POST",
        headers: { "Content-Type": "audio/wav" },
        body: wav,
        signal: controller.signal,
      });
      const result = await response.json();
      if (!response.ok)
        throw new Error(
          result.error?.message ||
            "Transcription failed. You can retry with your recording.",
        );
      if (typeof result.text !== "string" || !result.text.trim())
        throw new Error("No speech was detected. Record again.");
      if (mounted.current) {
        setTranscript(result.text);
        pendingAudio.current = null;
        setRetryAvailable(false);
      }
    } catch (err) {
      if (mounted.current)
        setError(
          err instanceof Error && err.name !== "AbortError"
            ? err.message
            : "Transcription timed out. You can retry with your recording.",
        );
    } finally {
      clearTimeout(timeout);
      if (mounted.current) setState("idle");
    }
  }
  function stop() {
    if (recorder.current?.state === "recording") recorder.current.stop();
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
  }
  async function start() {
    if (starting.current) return;
    starting.current = true;
    setState("accessing");
    setError(null);
    try {
      if (
        !navigator.mediaDevices?.getUserMedia ||
        typeof MediaRecorder === "undefined"
      )
        throw new Error(
          "Audio recording is unavailable in this browser. Use a recent Chrome, Edge, Firefox, or Safari browser.",
        );
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mounted.current) {
        media.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = media;
      const mimeType = [
        "audio/webm;codecs=opus",
        "audio/mp4",
        "audio/ogg;codecs=opus",
      ].find((type) => MediaRecorder.isTypeSupported(type));
      const capture = new MediaRecorder(media, {
        ...(mimeType ? { mimeType } : {}),
        audioBitsPerSecond: 64000,
      });
      recorder.current = capture;
      const parts: Blob[] = [];
      capture.ondataavailable = (event) => {
        if (event.data.size) parts.push(event.data);
      };
      capture.onerror = () => {
        capture.onstop = null;
        releaseMicrophone();
        setState("idle");
        setError("Audio recording stopped unexpectedly. Record again.");
      };
      capture.onstop = () => {
        releaseMicrophone();
        if (!mounted.current) return;
        const blob = new Blob(parts, { type: capture.mimeType });
        if (url.current) URL.revokeObjectURL(url.current);
        url.current = URL.createObjectURL(blob);
        setAudioUrl(url.current);
        pendingAudio.current = blob;
        setRetryAvailable(true);
        void transcribe(blob);
      };
      setTranscript("");
      pendingAudio.current = null;
      setRetryAvailable(false);
      if (url.current) {
        URL.revokeObjectURL(url.current);
        url.current = null;
        setAudioUrl(null);
      }
      capture.start(250);
      setState("recording");
      setSeconds(0);
      const started = performance.now();
      timer.current = setInterval(() => {
        const elapsed = Math.floor((performance.now() - started) / 1000);
        setSeconds(elapsed);
        if (elapsed >= 29) stop();
      }, 250);
    } catch (err) {
      releaseMicrophone();
      if (mounted.current) {
        setState("idle");
        setError(
          err instanceof DOMException && err.name === "NotAllowedError"
            ? "Microphone access was denied. Allow microphone access in your browser settings, then try again."
            : err instanceof Error
              ? err.message
              : "Could not access the microphone. Try again.",
        );
      }
    } finally {
      starting.current = false;
    }
  }
  const processing = state === "accessing" || state === "transcribing";
  return (
    <section className="voice-copilot-card" aria-labelledby="voice-title">
      <div className="voice-copilot-header">
        <div>
          <h3 id="voice-title" className="voice-copilot-title">
            Voice Copilot
          </h3>
          <p
            className="voice-status-caption"
            role={state === "idle" ? undefined : "status"}
            aria-live="polite"
          >
            {state === "idle" &&
              "Record a question, check the transcript, then analyze it."}
            {state === "accessing" && "Accessing microphone…"}
            {state === "recording" && `Recording… ${seconds} / 30 seconds`}
            {state === "transcribing" && "Transcribing your recording…"}
          </p>
        </div>
        <button
          type="button"
          className="voice-btn mic-btn"
          disabled={processing || busy}
          onClick={state === "recording" ? stop : start}
        >
          {state === "recording" ? "Stop & transcribe" : "Record Voice Note"}
        </button>
      </div>
      <p className="voice-context-pill">Active ticket: {ticketTitle}</p>
      {error && (
        <div className="voice-error-banner" role="alert">
          <span>{error}</span>
        </div>
      )}
      {audioUrl && (
        <div className="user-voice-card">
          <p>
            Your recording · available on this page until you leave or record
            again
          </p>
          <audio
            aria-label="Your voice recording"
            controls
            src={audioUrl}
            className="voice-note-audio-player"
          />
        </div>
      )}
      {state === "idle" && retryAvailable && (
        <button
          type="button"
          className="voice-btn"
          disabled={busy}
          onClick={() => {
            if (pendingAudio.current) void transcribe(pendingAudio.current);
          }}
        >
          Retry transcription
        </button>
      )}
      {transcript && (
        <div className="voice-transcription-underneath">
          <label htmlFor="voice-transcript">
            Review your transcript before analysis
          </label>
          <textarea
            id="voice-transcript"
            value={transcript}
            maxLength={500}
            rows={3}
            disabled={busy || state !== "idle"}
            onChange={(event) => setTranscript(event.target.value)}
          />
          <button
            type="button"
            className="voice-btn"
            disabled={busy || state !== "idle" || !transcript.trim()}
            onClick={() => void onAnalyze(transcript.trim())}
          >
            Analyze voice question
          </button>
          <p className="small muted">
            The answer and sources appear below. Only your explicit approval
            saves an internal note.
          </p>
        </div>
      )}
      <div className="voice-compliance-notice">
        <p>
          Audio is sent to Cloudflare for transcription when you stop recording.
          The recording stays on this page for playback and is not stored in our
          database. If you analyze it, your reviewed transcript and the AI
          result are saved in your demo session. AI replies in text.
          Transcription and analysis each use one AI request; the demo allows
          two requests per minute.
        </p>
      </div>
    </section>
  );
}
