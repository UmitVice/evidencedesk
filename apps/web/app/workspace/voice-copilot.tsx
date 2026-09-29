"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export type VoiceState =
  | "idle"
  | "connecting"
  | "listening"
  | "assistant_speaking"
  | "interrupted"
  | "error";

export interface SpokenTurn {
  id: string;
  role: "user" | "assistant";
  text: string;
  isFinal: boolean;
  timestamp: string;
}

export interface LiveCitation {
  source_id: string;
  title: string;
  heading: string;
  quote: string;
  score?: number;
}

export interface ProposedVoiceNote {
  content: string;
  proposal_id?: string;
  ticket_id?: string;
}

export interface VoiceCopilotProps {
  ticketId?: string;
  ticketTitle?: string;
  onNoteProposed?: (content: string, proposalId?: string) => void;
  onSelectSource?: (sourceId: string) => void;
}

export function VoiceCopilot({
  ticketId,
  ticketTitle,
  onNoteProposed,
  onSelectSource,
}: VoiceCopilotProps) {
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [transcripts, setTranscripts] = useState<SpokenTurn[]>([]);
  const [citations, setCitations] = useState<LiveCitation[]>([]);
  const [proposedNote, setProposedNote] = useState<ProposedVoiceNote | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const inputAudioCtxRef = useRef<AudioContext | null>(null);
  const outputAudioCtxRef = useRef<AudioContext | null>(null);
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const activeSourcesRef = useRef<AudioBufferSourceNode[]>([]);
  const nextPlayTimeRef = useRef<number>(0);
  const transcriptsBoxRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll transcripts inside its own container without scrolling the main page
  useEffect(() => {
    if (transcriptsBoxRef.current) {
      transcriptsBoxRef.current.scrollTop = transcriptsBoxRef.current.scrollHeight;
    }
  }, [transcripts]);

  // Clean stop all audio playback
  const stopPlayback = useCallback(() => {
    activeSourcesRef.current.forEach((source) => {
      try {
        source.stop();
        source.disconnect();
      } catch {
        // Source might already have ended
      }
    });
    activeSourcesRef.current = [];
    nextPlayTimeRef.current = 0;
  }, []);

  // Gracefully tear down all audio and websocket resources
  const disconnect = useCallback(() => {
    stopPlayback();

    if (wsRef.current) {
      try {
        if (wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: "control", action: "stop" }));
        }
        wsRef.current.close();
      } catch {
        // Ignore close errors
      }
      wsRef.current = null;
    }

    if (scriptProcessorRef.current) {
      try {
        scriptProcessorRef.current.disconnect();
      } catch {
        // Ignore
      }
      scriptProcessorRef.current = null;
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    if (inputAudioCtxRef.current) {
      try {
        inputAudioCtxRef.current.close();
      } catch {
        // Ignore
      }
      inputAudioCtxRef.current = null;
    }

    if (outputAudioCtxRef.current) {
      try {
        outputAudioCtxRef.current.close();
      } catch {
        // Ignore
      }
      outputAudioCtxRef.current = null;
    }

    setVoiceState("idle");
  }, [stopPlayback]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  // Playback PCM audio chunks received from assistant
  const playAudioChunk = useCallback((base64Pcm: string, sampleRate = 24000) => {
    if (!outputAudioCtxRef.current) {
      const AudioCtx =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      outputAudioCtxRef.current = new AudioCtx({ sampleRate });
    }

    const ctx = outputAudioCtxRef.current;
    if (ctx.state === "suspended") {
      void ctx.resume();
    }

    try {
      const binaryString = atob(base64Pcm);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      const int16Array = new Int16Array(bytes.buffer);
      const float32Array = new Float32Array(int16Array.length);
      for (let i = 0; i < int16Array.length; i++) {
        float32Array[i] = int16Array[i] / 32768.0;
      }

      const audioBuffer = ctx.createBuffer(1, float32Array.length, sampleRate);
      audioBuffer.getChannelData(0).set(float32Array);

      const sourceNode = ctx.createBufferSource();
      sourceNode.buffer = audioBuffer;
      sourceNode.connect(ctx.destination);

      const startTime = Math.max(ctx.currentTime, nextPlayTimeRef.current);
      sourceNode.start(startTime);
      nextPlayTimeRef.current = startTime + audioBuffer.duration;

      activeSourcesRef.current.push(sourceNode);
      setVoiceState("assistant_speaking");

      sourceNode.onended = () => {
        activeSourcesRef.current = activeSourcesRef.current.filter((s) => s !== sourceNode);
        if (activeSourcesRef.current.length === 0) {
          setVoiceState((prev) => (prev === "assistant_speaking" ? "listening" : prev));
        }
      };
    } catch (err) {
      console.warn("Failed to decode and play audio chunk:", err);
    }
  }, []);

  // Handle client-initiated barge-in interrupt
  const triggerBargeIn = useCallback(() => {
    stopPlayback();
    setVoiceState("interrupted");
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "control", action: "interrupt" }));
    }
    setTimeout(() => {
      setVoiceState((prev) => (prev === "interrupted" ? "listening" : prev));
    }, 600);
  }, [stopPlayback]);

  // Connect Voice Session
  const connect = useCallback(async () => {
    try {
      setErrorMessage(null);
      setVoiceState("connecting");
      setTranscripts([]);
      setCitations([]);
      setProposedNote(null);

      // 1. Acquire secure single-use voice ticket from Next.js BFF
      const ticketRes = await fetch("/api/voice/ticket", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!ticketRes.ok) {
        const errData = await ticketRes.json().catch(() => ({}));
        throw new Error(errData.error?.message || "Failed to acquire voice authorization ticket.");
      }

      const { ticket } = (await ticketRes.json()) as { ticket: string };

      // 2. Request microphone stream
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      // 3. Setup WebSocket connection using ticket
      const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const apiHost = window.location.port === "3000" ? "127.0.0.1:8000" : window.location.host;
      const wsUrl = `${wsProtocol}//${apiHost}/api/voice/session?ticket=${encodeURIComponent(ticket)}${
        ticketId ? `&ticket_id=${encodeURIComponent(ticketId)}` : ""
      }`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        // 4. Initialize input AudioContext and ScriptProcessor for streaming PCM
        const AudioCtx =
          window.AudioContext ||
          (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const inputCtx = new AudioCtx({ sampleRate: 16000 });
        inputAudioCtxRef.current = inputCtx;

        const source = inputCtx.createMediaStreamSource(stream);
        const processor = inputCtx.createScriptProcessor(2048, 1, 1);
        scriptProcessorRef.current = processor;

        processor.onaudioprocess = (e) => {
          if (ws.readyState !== WebSocket.OPEN) return;

          const inputData = e.inputBuffer.getChannelData(0);
          const pcmBuffer = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            const s = Math.max(-1, Math.min(1, inputData[i]));
            pcmBuffer[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
          }

          const bytes = new Uint8Array(pcmBuffer.buffer);
          let binary = "";
          for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
          }
          const base64Audio = btoa(binary);

          ws.send(
            JSON.stringify({
              type: "audio",
              data: base64Audio,
              sample_rate: 16000,
              channels: 1,
            })
          );
        };

        source.connect(processor);
        processor.connect(inputCtx.destination);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const timestamp = new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          });

          if (data.type === "control") {
            if (data.action === "start") {
              setVoiceState("listening");
            } else if (data.action === "interrupt") {
              stopPlayback();
              setVoiceState("interrupted");
              setTimeout(() => {
                setVoiceState((prev) => (prev === "interrupted" ? "listening" : prev));
              }, 600);
            } else if (data.action === "turn_complete") {
              if (activeSourcesRef.current.length === 0) {
                setVoiceState("listening");
              }
            } else if (data.action === "error") {
              setErrorMessage(data.message || "Voice engine encountered an error.");
              setVoiceState("error");
            }
          } else if (data.type === "transcript") {
            setTranscripts((prev) => {
              const role = data.role === "user" ? "user" : "assistant";
              return [
                ...prev,
                {
                  id: `${timestamp}-${Math.random()}`,
                  role,
                  text: data.text,
                  isFinal: Boolean(data.is_final),
                  timestamp,
                },
              ];
            });
          } else if (data.type === "citation") {
            if (Array.isArray(data.citations)) {
              setCitations((prev) => {
                const existingIds = new Set(prev.map((c) => c.source_id));
                const newCitations = data.citations.filter(
                  (c: LiveCitation) => !existingIds.has(c.source_id)
                );
                return [...prev, ...newCitations];
              });
            }
          } else if (data.type === "audio") {
            playAudioChunk(data.data, data.sample_rate || 24000);
          } else if (data.type === "tool_result") {
            if (data.name === "propose_ticket_note" && data.result) {
              setProposedNote({
                content: data.result.content || "",
                proposal_id: data.result.proposal_id,
                ticket_id: data.result.ticket_id,
              });
            }
          }
        } catch (err) {
          console.warn("Failed to process WebSocket event:", err);
        }
      };

      ws.onerror = () => {
        setErrorMessage("WebSocket connection error. Please verify the backend is running.");
        setVoiceState("error");
      };

      ws.onclose = (event) => {
        if (event.code === 1008) {
          setErrorMessage("Voice authorization failed. Please refresh your session.");
          setVoiceState("error");
        } else if (voiceState !== "error") {
          setVoiceState("idle");
        }
      };
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to start speech session. Check microphone access."
      );
      setVoiceState("error");
      disconnect();
    }
  }, [ticketId, disconnect, playAudioChunk, stopPlayback, voiceState]);

  const isConnected = voiceState !== "idle" && voiceState !== "error";

  return (
    <div className="voice-copilot-card">
      <div className="voice-copilot-header">
        <div className="voice-status-group">
          <div className={`status-indicator ${voiceState}`} aria-hidden="true">
            <span className="indicator-pulse" />
          </div>
          <div>
            <h3 className="voice-copilot-title">Voice Copilot</h3>
            <p className="voice-status-caption">
              {voiceState === "idle" && "Ready to start live speech session"}
              {voiceState === "connecting" && "Establishing encrypted voice channel…"}
              {voiceState === "listening" && "Listening… speak naturally into your microphone"}
              {voiceState === "assistant_speaking" && "Assistant speaking…"}
              {voiceState === "interrupted" && "Interrupted by speech"}
              {voiceState === "error" && "Session interrupted"}
            </p>
          </div>
        </div>

        <div className="voice-actions-group">
          {voiceState === "assistant_speaking" && (
            <button
              type="button"
              className="voice-btn interrupt-btn"
              onClick={triggerBargeIn}
              title="Interrupt speech"
            >
              Interrupt
            </button>
          )}

          <button
            type="button"
            className={`voice-btn mic-btn ${isConnected ? "active" : ""}`}
            onClick={isConnected ? disconnect : connect}
            disabled={voiceState === "connecting"}
            aria-label={isConnected ? "End Voice Session" : "Start Voice Session"}
          >
            <span className="mic-icon" aria-hidden="true">
              {isConnected ? "⏹" : "🎙"}
            </span>
            <span>{isConnected ? "Disconnect" : "Talk with Copilot"}</span>
          </button>
        </div>
      </div>

      {ticketTitle && (
        <div className="voice-context-pill">
          <span className="pill-label">Context:</span>
          <span className="pill-ticket">{ticketTitle}</span>
        </div>
      )}

      {errorMessage && (
        <div className="voice-error-banner" role="alert">
          <span>{errorMessage}</span>
          <button type="button" onClick={() => setErrorMessage(null)} className="dismiss-btn">
            ✕
          </button>
        </div>
      )}

      {/* Spoken Dialogue Transcript Box */}
      {isConnected && (
        <div ref={transcriptsBoxRef} className="voice-transcripts-box" aria-live="polite">
          {transcripts.length === 0 ? (
            <div className="transcripts-placeholder">
              <p>Say something like: &ldquo;How should we recover stopped webhook delivery retries?&rdquo;</p>
              <span className="audio-wave-hint">Listening for speech…</span>
            </div>
          ) : (
            transcripts.map((turn) => (
              <div key={turn.id} className={`transcript-bubble ${turn.role}`}>
                <div className="transcript-meta">
                  <span className="transcript-speaker">
                    {turn.role === "user" ? "You" : "Voice Copilot"}
                  </span>
                  <span className="transcript-time">{turn.timestamp}</span>
                </div>
                <div className="transcript-text">{turn.text}</div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Live Citations Stream */}
      {citations.length > 0 && (
        <div className="voice-citations-container">
          <h4 className="citations-header">Retrieved Knowledge Citations</h4>
          <div className="citations-grid">
            {citations.map((c) => (
              <div
                key={c.source_id}
                className="voice-citation-card"
                onClick={() => onSelectSource?.(c.source_id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    onSelectSource?.(c.source_id);
                  }
                }}
              >
                <div className="citation-title">{c.title}</div>
                <div className="citation-heading">{c.heading}</div>
                <blockquote className="citation-quote">&ldquo;{c.quote}&rdquo;</blockquote>
                <span className="citation-action">Inspect Source →</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Proposed Note Banner */}
      {proposedNote && (
        <div className="voice-proposal-banner">
          <div className="proposal-header">
            <span className="proposal-tag">Voice Drafted Note</span>
            <span className="proposal-status">Pending Review</span>
          </div>
          <div className="proposal-content">{proposedNote.content}</div>
          <div className="proposal-actions">
            <button
              type="button"
              className="apply-proposal-btn"
              onClick={() => {
                onNoteProposed?.(proposedNote.content, proposedNote.proposal_id);
              }}
            >
              Use Note in Draft Workspace
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
