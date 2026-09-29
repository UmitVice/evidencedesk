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
  audioUrl?: string;
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
  const [recordingUrl, setRecordingUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedBlobsRef = useRef<Blob[]>([]);
  const inputAudioCtxRef = useRef<AudioContext | null>(null);
  const scriptProcessorRef = useRef<ScriptProcessorNode | null>(null);
  const transcriptsBoxRef = useRef<HTMLDivElement | null>(null);

  // Auto-scroll transcripts inside its own container without scrolling the main window
  useEffect(() => {
    if (transcriptsBoxRef.current) {
      transcriptsBoxRef.current.scrollTop = transcriptsBoxRef.current.scrollHeight;
    }
  }, [transcripts]);

  // Clean stop any ongoing audio/speech
  const stopPlayback = useCallback(() => {
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      try {
        window.speechSynthesis.cancel();
      } catch {
        // Ignore
      }
    }
  }, []);

  // Flush and attach current recorded user audio to latest user turn
  const saveUserTurnAudio = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      try {
        mediaRecorderRef.current.requestData();
      } catch {
        // Ignore
      }
    }
    if (recordedBlobsRef.current.length > 0) {
      const mimeType = recordedBlobsRef.current[0].type || "audio/webm";
      const audioBlob = new Blob([...recordedBlobsRef.current], { type: mimeType });
      const url = URL.createObjectURL(audioBlob);
      setRecordingUrl(url);
      setTranscripts((prev) => {
        const updated = [...prev];
        for (let i = updated.length - 1; i >= 0; i--) {
          if (updated[i].role === "user") {
            updated[i] = { ...updated[i], audioUrl: updated[i].audioUrl || url };
            break;
          }
        }
        return updated;
      });
      return url;
    }
    return null;
  }, []);

  // Gracefully complete the call, save user audio recording, and keep dialogue visible
  const completeCall = useCallback(() => {
    stopPlayback();

    // 1. Stop MediaRecorder and generate playable audio blob for user voice message
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      try {
        mediaRecorderRef.current.onstop = () => {
          if (recordedBlobsRef.current.length > 0) {
            const mimeType = recordedBlobsRef.current[0].type || "audio/webm";
            const audioBlob = new Blob(recordedBlobsRef.current, { type: mimeType });
            const url = URL.createObjectURL(audioBlob);
            setRecordingUrl(url);
            setTranscripts((prev) =>
              prev.map((t) => (t.role === "user" ? { ...t, audioUrl: t.audioUrl || url } : t))
            );
          }
        };
        mediaRecorderRef.current.stop();
      } catch (err) {
        console.warn("Error stopping MediaRecorder:", err);
      }
      mediaRecorderRef.current = null;
    } else if (recordedBlobsRef.current.length > 0) {
      const mimeType = recordedBlobsRef.current[0].type || "audio/webm";
      const audioBlob = new Blob(recordedBlobsRef.current, { type: mimeType });
      const url = URL.createObjectURL(audioBlob);
      setRecordingUrl(url);
      setTranscripts((prev) =>
        prev.map((t) => (t.role === "user" ? { ...t, audioUrl: t.audioUrl || url } : t))
      );
    }

    // 2. Close WebSocket gracefully
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

    // 3. Disconnect audio capture processor
    if (scriptProcessorRef.current) {
      try {
        scriptProcessorRef.current.disconnect();
      } catch {
        // Ignore
      }
      scriptProcessorRef.current = null;
    }

    // 4. Stop microphone tracks
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
    }

    // 5. Close audio contexts
    if (inputAudioCtxRef.current) {
      try {
        void inputAudioCtxRef.current.close();
      } catch {
        // Ignore
      }
      inputAudioCtxRef.current = null;
    }

    setVoiceState("idle");
  }, [stopPlayback]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      completeCall();
    };
  }, [completeCall]);
  const triggerBargeIn = useCallback(() => {
    stopPlayback();
    setVoiceState("interrupted");
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "control", action: "interrupt" }));
    }
    setTimeout(() => {
      setVoiceState((prev) => (prev === "interrupted" ? "listening" : prev));
    }, 500);
  }, [stopPlayback]);

  // Connect Voice Session
  const connect = useCallback(async () => {
    try {
      setErrorMessage(null);
      setVoiceState("connecting");
      recordedBlobsRef.current = [];

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

      // 3. Initialize MediaRecorder for full call playback
      try {
        const mimeType = MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : MediaRecorder.isTypeSupported("audio/mp4")
          ? "audio/mp4"
          : "";
        const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
        recorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) {
            recordedBlobsRef.current.push(e.data);
          }
        };
        recorder.start(500);
        mediaRecorderRef.current = recorder;
      } catch (recErr) {
        console.warn("MediaRecorder start failed:", recErr);
      }

      // 4. Setup WebSocket connection using single-use ticket
      const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const apiHost = window.location.port === "3000" ? "127.0.0.1:8000" : window.location.host;
      const wsUrl = `${wsProtocol}//${apiHost}/api/voice/session?ticket=${encodeURIComponent(ticket)}${
        ticketId ? `&ticket_id=${encodeURIComponent(ticketId)}` : ""
      }`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        // 5. Initialize input AudioContext and ScriptProcessor for streaming PCM
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
              }, 500);
            } else if (data.action === "turn_complete") {
              saveUserTurnAudio();
              setVoiceState("listening");
            } else if (data.action === "error") {
              setErrorMessage(data.message || "Voice engine encountered an error.");
              setVoiceState("error");
            }
          } else if (data.type === "transcript") {
            setTranscripts((prev) => {
              const role = data.role === "user" ? "user" : "assistant";
              const last = prev[prev.length - 1];

              // Update in-progress assistant speech bubble
              if (last && last.role === role && !last.isFinal) {
                return [
                  ...prev.slice(0, -1),
                  {
                    ...last,
                    text: data.text,
                    isFinal: Boolean(data.is_final),
                    timestamp,
                  },
                ];
              }

              // Avoid exact duplicate bubbles
              if (last && last.role === role && last.text === data.text) {
                return prev;
              }

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

            // If assistant begins or finishes response, flush user audio to bubble
            if (data.role === "assistant") {
              saveUserTurnAudio();
              setVoiceState("assistant_speaking");
            }
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
            // Intentionally silent: AI produces text response without synthesized robotic sound
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
      completeCall();
    }
  }, [ticketId, completeCall, saveUserTurnAudio, stopPlayback, voiceState]);

  const isConnected = voiceState !== "idle" && voiceState !== "error";
  const hasDialogue = transcripts.length > 0;

  // Copy full transcript text to clipboard
  const copyTranscript = useCallback(() => {
    if (transcripts.length === 0) return;
    const formatted = transcripts
      .map(
        (t) =>
          `[${t.timestamp}] ${t.role === "user" ? "Agent/User" : "Voice Copilot"}:\n${t.text}`
      )
      .join("\n\n");
    void navigator.clipboard.writeText(formatted);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [transcripts]);

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
              {voiceState === "idle" &&
                (hasDialogue
                  ? "Voice note saved · Click play on your message to listen"
                  : "Ready to record voice note · AI will reply silently in text")}
              {voiceState === "connecting" && "Accessing microphone…"}
              {voiceState === "listening" && "Recording your voice… speak into your microphone"}
              {voiceState === "assistant_speaking" && "AI generated response (silent)"}
              {voiceState === "interrupted" && "Interrupted by user speech"}
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
              title="Interrupt AI"
            >
              Interrupt
            </button>
          )}

          <button
            type="button"
            className={`voice-btn mic-btn ${isConnected ? "active" : ""}`}
            onClick={isConnected ? completeCall : connect}
            disabled={voiceState === "connecting"}
            aria-label={isConnected ? "Save & Disconnect Voice Note" : "Record Voice Note"}
          >
            <span className="mic-icon" aria-hidden="true">
              {isConnected ? "⏹" : "🎙"}
            </span>
            <span>
              {isConnected
                ? "Save & Disconnect"
                : hasDialogue
                ? "Record Another Voice Note"
                : "Record Voice Note"}
            </span>
          </button>
        </div>
      </div>

      {ticketTitle && (
        <div className="voice-context-pill">
          <span className="pill-label">Active Ticket Context:</span>
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

      {/* Spoken Dialogue Transcript Box - Preserved after call ends */}
      {(isConnected || hasDialogue) && (
        <div className="transcripts-wrapper">
          <div className="transcripts-header-bar">
            <span className="transcripts-title">Spoken Dialogue Transcript</span>
            {hasDialogue && (
              <button
                type="button"
                className="copy-transcript-btn"
                onClick={copyTranscript}
                title="Copy entire transcript text"
              >
                {copied ? "✓ Copied to clipboard" : "📋 Copy Transcript"}
              </button>
            )}
          </div>

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
                      {turn.role === "user" ? "You (Voice Note)" : "Voice Copilot (AI)"}
                    </span>
                    <span className="transcript-time">{turn.timestamp}</span>
                  </div>

                  {turn.role === "user" ? (
                    <div className="user-voice-card">
                      {/* Voice audio player on top: Click to listen to user's recorded speech */}
                      <div className="voice-player-row">
                        {turn.audioUrl || recordingUrl ? (
                          <audio
                            controls
                            src={turn.audioUrl || recordingUrl || undefined}
                            className="voice-note-audio-player"
                            preload="metadata"
                          >
                            Your browser does not support audio playback.
                          </audio>
                        ) : isConnected ? (
                          <div className="recording-in-progress-pill">
                            <span className="rec-dot" aria-hidden="true">●</span>
                            <span>Recording your voice note… (audio player ready when saved)</span>
                          </div>
                        ) : (
                          <span className="voice-audio-fallback-note">Voice note recorded</span>
                        )}
                      </div>

                      {/* Transcribed text underneath */}
                      <div className="voice-transcription-underneath">
                        <span className="transcription-label">Transcribed Speech</span>
                        <div className="transcript-text">{turn.text}</div>
                      </div>
                    </div>
                  ) : (
                    <div className="assistant-message-card">
                      <div className="transcript-text">{turn.text}</div>
                      <span className="assistant-silent-tag">Silent AI response · No voice audio played</span>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Live Citations Stream */}
      {citations.length > 0 && (
        <div className="voice-citations-container">
          <h4 className="citations-header">Retrieved Knowledge Citations ({citations.length})</h4>
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
                <span className="citation-action">Inspect Source Document →</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Proposed Note Banner */}
      {proposedNote && (
        <div className="voice-proposal-banner">
          <div className="proposal-header">
            <span className="proposal-tag">Voice Drafted Resolution Note</span>
            <span className="proposal-status">Pending Your Approval</span>
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
              Use Note in Ticket Workspace
            </button>
          </div>
        </div>
      )}

      {/* Privacy & Legal Compliance Notice */}
      <div className="voice-compliance-notice">
        <span className="compliance-icon" aria-hidden="true">🛡️</span>
        <p>
          <strong>Voice Note & Compliance Notice:</strong> Your recorded voice audio and transcript are preserved
          locally in your active browser session for quality audit and support resolution. The AI assistant responds
          strictly in silent text. No biometric data is retained or processed by external parties.
        </p>
      </div>
    </div>
  );
}
