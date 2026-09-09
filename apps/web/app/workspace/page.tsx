"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import type {
  TicketSummary,
  TicketResponse,
  TicketsResponse,
  RunResponse,
  SourceResponse,
} from "../../lib/api-contract";

class ApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
  ) {
    super(message);
  }
}
async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  const data = await response.json();
  if (!response.ok)
    throw new ApiError(
      data.error?.message || "The request failed safely.",
      data.error?.code || "request_failed",
    );
  return data as T;
}
function requestedSample() {
  const sample = new URLSearchParams(window.location.search).get("sample");
  return sample && ["webhook", "credential", "export"].includes(sample)
    ? sample
    : null;
}
const eventLabels: Record<string, string> = {
  proposed: "Note proposed",
  applied: "Note approved and saved",
  rejected: "Proposal rejected",
};

export default function Workspace() {
  const [tickets, setTickets] = useState<TicketSummary[]>([]);
  const [ticket, setTicket] = useState<TicketResponse | null>(null);
  const [run, setRun] = useState<RunResponse | null>(null);
  const [mode, setMode] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [source, setSource] = useState<
    (SourceResponse & { claim: string; quote: string }) | null
  >(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const sourceOpener = useRef<HTMLButtonElement | null>(null);
  const generation = useRef(0);
  const opening = useRef<Promise<TicketsResponse> | null>(null);

  const select = useCallback(async (id: string) => {
    const request = ++generation.current;
    const detail = await api<TicketResponse>(`tickets/${id}`);
    const latest = detail.runs[0]
      ? await api<RunResponse>(`runs/${detail.runs[0].id}`)
      : null;
    if (request !== generation.current) return;
    setTicket(detail);
    setRun(latest);
    setQuestion("");
    sessionStorage.setItem("evidencedesk_ticket", id);
    window.history.replaceState(
      null,
      "",
      `/workspace?sample=${encodeURIComponent(detail.sample)}`,
    );
  }, []);
  const restore = useCallback(
    async (data: TicketsResponse) => {
      setTickets(data.tickets);
      setMode(data.mode);
      const previous = sessionStorage.getItem("evidencedesk_ticket");
      const selected =
        data.tickets.find((t) => t.sample === requestedSample()) ||
        data.tickets.find((t) => t.id === previous) ||
        data.tickets.find((t) => t.sample === "webhook") ||
        data.tickets[0];
      if (selected) await select(selected.id);
      setReady(true);
    },
    [select],
  );
  useEffect(() => {
    let cancelled = false;
    // Share the in-flight bootstrap across React's development effect replay.
    if (!opening.current)
      opening.current = api<TicketsResponse>("tickets").catch(async (e) => {
        if (
          requestedSample() &&
          e instanceof ApiError &&
          e.code === "session_expired"
        ) {
          await api("sessions", {});
          return api<TicketsResponse>("tickets");
        }
        throw e;
      });
    opening.current
      .then(async (data) => {
        if (!cancelled) await restore(data);
      })
      .catch((e) => {
        if (
          !cancelled &&
          (!(e instanceof ApiError) || e.code !== "session_expired")
        )
          setError(
            e instanceof Error ? e.message : "The sandbox is unavailable.",
          );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [restore]);

  async function act(operation: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await operation();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed.");
      if (e instanceof ApiError && e.code === "session_expired") {
        setReady(false);
        setMode(null);
        setRun(null);
      }
    } finally {
      setBusy(false);
    }
  }
  async function start() {
    await api("sessions", {});
    await restore(await api<TicketsResponse>("tickets"));
  }
  async function analyze() {
    if (!ticket) return;
    setRun(null);
    try {
      setRun(
        await api<RunResponse>(`tickets/${ticket.id}/analyze`, { question }),
      );
    } finally {
      const detail = await api<TicketResponse>(`tickets/${ticket.id}`);
      setTicket(detail);
      if (detail.runs[0])
        setRun(await api<RunResponse>(`runs/${detail.runs[0].id}`));
    }
  }
  async function decide(decision: "approve" | "reject") {
    if (!run?.proposal || !ticket) return;
    await api(`proposals/${run.proposal.id}/decision`, { decision });
    setRun(await api<RunResponse>(`runs/${run.id}`));
    setTicket(await api<TicketResponse>(`tickets/${ticket.id}`));
  }
  async function inspect(id: string, claim: string, quote: string) {
    if (!run) return;
    const data = await api<SourceResponse>(`runs/${run.id}/sources/${id}`);
    setSource({ ...data, claim, quote });
    dialog.current?.showModal();
  }
  const completedLive = run?.mode === "live" && run.status === "complete";
  const status =
    error || run?.status === "failed"
      ? "Unavailable"
      : completedLive
        ? Number(run.trace.attempts) > 0
          ? "Live AI"
          : "Live retrieval"
        : mode === "live"
          ? "Ready for live analysis"
          : mode === "simulated"
            ? "Simulated demo — no model called"
            : loading
              ? "Connecting…"
              : "Not connected";
  const stale =
    run?.proposal?.status === "pending" &&
    run.proposal.expected_version !== ticket?.version;
  return (
    <>
      <section className="workspace-title">
        <div>
          <p className="eyebrow">Investigation desk</p>
          <h1>From ticket to a reviewed note.</h1>
        </div>
        <span
          className={`badge ${completedLive && !error ? "verified" : ""}`}
          data-testid="analysis-mode"
        >
          {status}
        </span>
      </section>
      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      {loading ? (
        <div className="card connection-state" role="status">
          Opening your investigation…
        </div>
      ) : !ready ? (
        <section className="card session-start">
          <p className="eyebrow">A private synthetic session</p>
          <h2>Choose a ticket. Start investigating.</h2>
          <p>
            Three fictional tickets, a source-backed answer, and a note you can
            approve or reject. Your session expires within 24 hours.
          </p>
          <button disabled={busy} onClick={() => act(start)}>
            {busy ? "Starting…" : "Start sandbox session"}
          </button>
          <p className="small muted">
            Analysis runs only when you select Analyze ticket. Starting a
            session does not call a model.
          </p>
          <Link className="text-link" href="/">
            Back to sample cases
          </Link>
        </section>
      ) : (
        <div className="workspace-grid" aria-busy={busy}>
          <aside
            className="card ticket-context"
            aria-labelledby="ticket-heading"
          >
            <p className="eyebrow">01 / Ticket context</p>
            <label htmlFor="ticket-picker">Choose ticket</label>
            <select
              id="ticket-picker"
              value={ticket?.id || ""}
              disabled={busy}
              onChange={(e) => act(() => select(e.target.value))}
            >
              {tickets.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.title}
                </option>
              ))}
            </select>
            <div className="ticket-heading">
              <span className="case-category">{ticket?.sample}</span>
              <h2 id="ticket-heading">{ticket?.title}</h2>
            </div>
            <p className="ticket-body">{ticket?.body}</p>
            <dl className="ticket-meta">
              <div>
                <dt>Customer</dt>
                <dd>Harbor / RelayNest</dd>
              </div>
              <div>
                <dt>Data</dt>
                <dd>Synthetic sandbox</dd>
              </div>
              <div>
                <dt>Ticket version</dt>
                <dd>{ticket?.version}</dd>
              </div>
              <div>
                <dt>Saved notes</dt>
                <dd>{ticket?.notes.length ?? 0}</dd>
              </div>
            </dl>
            <p className="small muted">
              This desk saves internal notes only. It cannot replay a webhook,
              rotate a credential, or contact a customer.
            </p>
          </aside>
          <section className="workspace-center" aria-label="Ticket analysis">
            <article className="card investigation">
              <p className="eyebrow">02 / AI investigation</p>
              <h2>Investigate the question.</h2>
              <label htmlFor="question">Optional question</label>
              {mode === "simulated" ? (
                <select
                  id="question"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  disabled={busy}
                >
                  <option value="">Use the ticket question</option>
                  <option>What should we do?</option>
                  <option>Can RelayNest configure SSO?</option>
                </select>
              ) : (
                <textarea
                  id="question"
                  maxLength={500}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  disabled={busy}
                  placeholder="Leave blank to investigate the ticket question"
                />
              )}
              <div className="actions">
                <button disabled={busy} onClick={() => act(analyze)}>
                  {busy ? "Working…" : "Analyze ticket"}
                </button>
                <span className="small muted">
                  Up to two analyses per minute
                </span>
              </div>
              <div className="answer" aria-live="polite">
                {!run ? (
                  <div className="answer-empty">
                    <span className="small muted">
                      {busy
                        ? "Retrieving evidence and checking the answer…"
                        : "No analysis yet"}
                    </span>
                    <p>
                      Claims and their supporting passages will appear here.
                      Analysis alone never saves a note.
                    </p>
                  </div>
                ) : run.status === "failed" ? (
                  <div className="notice error" role="alert">
                    Analysis failed safely: {run.error_code}. No executable note
                    was created. No simulated answer was substituted.
                  </div>
                ) : run.status === "running" ? (
                  <p>
                    This analysis has not completed. Refresh to check its stored
                    state. You can start a new analysis within the quota.
                  </p>
                ) : (
                  <>
                    <div className="answer-heading">
                      <h3>Suggested answer</h3>
                      <span className="badge">
                        {run.mode === "live"
                          ? "Live result"
                          : "Simulated result"}
                      </span>
                    </div>
                    {run.result?.status === "insufficient_evidence" ? (
                      <>
                        <h3>Insufficient evidence</h3>
                        <p>
                          The available documentation does not support an
                          answer. No internal note is proposed. Ask for an
                          official product clarification.
                        </p>
                      </>
                    ) : (
                      run.result?.claims.map((claim, i) => (
                        <div className="claim" key={i}>
                          <span className="claim-number">Claim {i + 1}</span>
                          <p>{claim.text}</p>
                          {claim.citations.map((citation, j) => (
                            <button
                              key={j}
                              disabled={busy}
                              className="source-link secondary"
                              onClick={(event) => {
                                sourceOpener.current = event.currentTarget;
                                act(() =>
                                  inspect(
                                    citation.source_id,
                                    claim.text,
                                    citation.quote,
                                  ),
                                );
                              }}
                            >
                              Inspect evidence {i + 1}.{j + 1}{" "}
                              <span aria-hidden="true">↗</span>
                            </button>
                          ))}
                        </div>
                      ))
                    )}
                    <p className="small muted integrity-note">
                      Source and exact-quote checks passed. They do not prove
                      the answer is correct; review the evidence and proposed
                      note.
                    </p>
                  </>
                )}
              </div>
            </article>
            <article
              className="card saved-notes"
              aria-labelledby="saved-notes-title"
            >
              <p className="eyebrow">Persisted ticket data</p>
              <h2 id="saved-notes-title">Saved internal notes</h2>
              {ticket?.notes.length ? (
                ticket.notes.map((note) => (
                  <div className="saved-note" key={note.id}>
                    <span className="badge">Saved after approval</span>
                    <blockquote>{note.content}</blockquote>
                    <time className="small muted" dateTime={note.created_at}>
                      {new Date(note.created_at).toLocaleString()}
                    </time>
                  </div>
                ))
              ) : (
                <p className="muted">
                  No notes saved. Analysis alone never changes the ticket.
                </p>
              )}
            </article>
          </section>
          <aside className="workspace-right">
            <section className="card approval" aria-labelledby="proposal-title">
              <p className="eyebrow">03 / Your decision</p>
              <h2 id="proposal-title">Proposed internal note</h2>
              {run?.proposal ? (
                <>
                  <span className="badge">
                    {stale ? "Needs a new analysis" : run.proposal.status}
                  </span>
                  <blockquote className="proposed-note">
                    {run.proposal.content}
                  </blockquote>
                  <p className="small muted">
                    This exact text will be saved if approved. Applies to ticket
                    version {run.proposal.expected_version}; expires{" "}
                    {new Date(run.proposal.expires_at).toLocaleTimeString()}.
                  </p>
                  {run.proposal.status === "pending" ? (
                    stale ? (
                      <p className="notice">
                        This proposal is stale or expired. Analyze the ticket
                        again before deciding.
                      </p>
                    ) : (
                      <div className="decision-actions">
                        <button
                          disabled={busy}
                          onClick={() => act(() => decide("approve"))}
                        >
                          Approve and add note
                        </button>
                        <button
                          className="secondary"
                          disabled={busy}
                          onClick={() => act(() => decide("reject"))}
                        >
                          Reject proposal
                        </button>
                      </div>
                    )
                  ) : (
                    <p role="status">
                      {run.proposal.status === "applied"
                        ? "The exact approved note is saved."
                        : "Rejected. The ticket was not changed."}
                    </p>
                  )}
                  <details>
                    <summary>Content fingerprint</summary>
                    <code className="hash">{run.proposal.content_hash}</code>
                  </details>
                </>
              ) : (
                <div className="proposal-empty">
                  <p>No proposed note yet.</p>
                  <p className="small muted">
                    A validated proposal appears after analysis. Read it
                    alongside the evidence before deciding.
                  </p>
                </div>
              )}
            </section>
            <section className="card audit" aria-labelledby="audit-title">
              <p className="eyebrow">Decision history</p>
              <h2 id="audit-title">Audit timeline</h2>
              {ticket?.audit.length ? (
                <ol className="timeline">
                  {ticket.audit.map((event, i) => (
                    <li key={i}>
                      <strong>{eventLabels[event.event] || event.event}</strong>
                      <time dateTime={event.created_at}>
                        {new Date(event.created_at).toLocaleTimeString()}
                      </time>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="small muted">
                  Proposals and decisions will be recorded here.
                </p>
              )}
            </section>
          </aside>
        </div>
      )}
      <dialog
        ref={dialog}
        onClose={() => sourceOpener.current?.focus()}
        aria-labelledby="source-title"
        className="source-drawer"
      >
        <button
          className="secondary close"
          onClick={() => dialog.current?.close()}
          aria-label="Close source"
        >
          Close <span aria-hidden="true">×</span>
        </button>
        <p className="eyebrow">Evidence inspection</p>
        <h2 id="source-title">{source?.title}</h2>
        <p className="source-meta">
          <span className="badge">Version {source?.version}</span>
          <span className="badge">{source?.status}</span>
        </p>
        <section className="claim-context">
          <h3>Claim under review</h3>
          <p>{source?.claim}</p>
        </section>
        <h3>Quoted evidence</h3>
        <blockquote className="exact-quote">{source?.quote}</blockquote>
        <details open>
          <summary>Full passage · {source?.heading}</summary>
          <p className="source-passage">{source?.body}</p>
        </details>
        <p className="small muted">
          Source: {source?.source_id}. This is the original authorized passage
          captured for this analysis, not a generated explanation.
        </p>
      </dialog>
    </>
  );
}
