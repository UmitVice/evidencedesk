"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import type {
  TicketSummary,
  TicketResponse,
  TicketsResponse,
  RunResponse,
  SourceResponse,
} from "../../lib/api-contract";

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(data.error?.message || "The request failed safely.");
  return data as T;
}
export default function Workspace() {
  const [tickets, setTickets] = useState<TicketSummary[]>([]);
  const [ticket, setTicket] = useState<TicketResponse | null>(null);
  const [run, setRun] = useState<RunResponse | null>(null);
  const [mode, setMode] = useState("simulated");
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [source, setSource] = useState<SourceResponse | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const generation = useRef(0);
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
  }, []);
  const restore = useCallback(async () => {
    const data = await api<TicketsResponse>("tickets");
    setTickets(data.tickets);
    setMode(data.mode);
    const previous = sessionStorage.getItem("evidencedesk_ticket");
    const selected =
      data.tickets.find((t) => t.id === previous) || data.tickets[0];
    if (selected) await select(selected.id);
    setReady(true);
  }, [select]);
  useEffect(() => {
    let cancelled = false;
    api<TicketsResponse>("tickets")
      .then(async (data) => {
        if (cancelled) return;
        setTickets(data.tickets);
        setMode(data.mode);
        const previous = sessionStorage.getItem("evidencedesk_ticket");
        const selected =
          data.tickets.find((t) => t.id === previous) || data.tickets[0];
        if (selected) await select(selected.id);
        if (!cancelled) setReady(true);
      })
      .catch(() => {
        if (!cancelled) setReady(false);
      });
    return () => {
      cancelled = true;
    };
  }, [select]);
  async function act(operation: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await operation();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  }
  async function start() {
    await api("sessions", {});
    await restore();
  }
  async function analyze() {
    if (!ticket) return;
    const result = await api<RunResponse>(`tickets/${ticket.id}/analyze`, {
      question,
    });
    setRun(result);
    setTicket(await api<TicketResponse>(`tickets/${ticket.id}`));
  }
  async function decide(decision: "approve" | "reject") {
    if (!run?.proposal || !ticket) return;
    await api(`proposals/${run.proposal.id}/decision`, { decision });
    setRun(await api<RunResponse>(`runs/${run.id}`));
    setTicket(await api<TicketResponse>(`tickets/${ticket.id}`));
  }
  async function inspect(id: string) {
    const data = await api<SourceResponse>(`sources/${id}`);
    setSource(data);
    dialog.current?.showModal();
  }
  return (
    <>
      <section className="workspace-title">
        <div>
          <p className="eyebrow">Support workspace</p>
          <h1>Understand. Inspect. Decide.</h1>
        </div>
        <span className="badge">
          {mode === "live" ? "Live AI" : "Simulated demo — no model called"}
        </span>
      </section>
      {error && (
        <div className="notice error" role="alert">
          {error}
        </div>
      )}
      {!ready ? (
        <section className="card">
          <h2>Your own support sandbox</h2>
          <p>
            Start an isolated session with three synthetic tickets. Your notes
            and decisions are saved only in this session and expire within 24
            hours.
          </p>
          <button disabled={busy} onClick={() => act(start)}>
            {busy ? "Starting…" : "Start sandbox session"}
          </button>
          <div className="walkthrough">
            <p className="eyebrow">Static walkthrough · no database mutation</p>
            <h3>A webhook delivery has exhausted its retries.</h3>
            <p>
              Read the ticket → retrieve retry guidance → inspect the original
              excerpt → review a proposed internal note → approve or reject.
            </p>
            <p className="muted">
              If the database is unavailable, this walkthrough remains
              available. It does not simulate a successful write.
            </p>
          </div>
        </section>
      ) : (
        <div className="workspace-grid">
          <aside className="card ticket-list">
            <p className="eyebrow">Your tickets · {tickets.length}</p>
            {tickets.map((t) => (
              <button
                key={t.id}
                className={`ticket-choice ${ticket?.id === t.id ? "selected" : ""}`}
                disabled={busy}
                aria-pressed={ticket?.id === t.id}
                onClick={() => act(() => select(t.id))}
              >
                <span className="ticket-kind">{t.sample}</span>
                {t.title}
                <span className="muted">Open ticket →</span>
              </button>
            ))}
            <p className="muted small">
              RelayNest / Harbor
              <br />
              Fictional customer data
            </p>
          </aside>
          <section className="workspace-center" aria-label="Ticket analysis">
            <article className="card">
              <p className="eyebrow">
                Selected ticket · version {ticket?.version}
              </p>
              <h2>{ticket?.title}</h2>
              <p>{ticket?.body}</p>
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
                  placeholder="Ask a focused product question"
                />
              )}
              <div className="actions">
                <button disabled={busy} onClick={() => act(analyze)}>
                  {busy ? "Working…" : "Analyze ticket"}
                </button>
                <span className="muted small">
                  Up to two analyses per minute
                </span>
              </div>
            </article>
            <article className="card answer" aria-live="polite">
              <p className="eyebrow">Answer & evidence</p>
              {!run ? (
                <>
                  <h2>A clear answer starts with evidence.</h2>
                  <p className="muted">
                    Analyze this ticket to retrieve authorized product
                    documentation. Each factual claim will link to its
                    supporting excerpt.
                  </p>
                </>
              ) : run.status === "failed" ? (
                <p role="alert">
                  Analysis failed safely: {run.error_code}. No executable note
                  was created.
                </p>
              ) : run.status === "running" ? (
                <p>
                  This analysis has not completed. Refresh to check its stored
                  state. If it remains interrupted, analyze again within the
                  quota.
                </p>
              ) : (
                <>
                  <span className="badge">
                    {run.mode === "live"
                      ? "Live AI"
                      : "Simulated demo — no model called"}
                  </span>
                  {run.result?.status === "insufficient_evidence" ? (
                    <>
                      <h2>Insufficient evidence</h2>
                      <p>
                        The available documentation does not support an answer.
                        No internal note is proposed. Ask for an official
                        product clarification.
                      </p>
                    </>
                  ) : (
                    run.result?.claims.map((claim, i) => (
                      <div key={i} className="claim">
                        <p>{claim.text}</p>
                        {claim.citations.map((citation, j) => (
                          <button
                            key={j}
                            className="source-link secondary"
                            onClick={() =>
                              act(() => inspect(citation.source_id))
                            }
                          >
                            [{j + 1}] Inspect supporting excerpt ↗
                          </button>
                        ))}
                      </div>
                    ))
                  )}
                  <p className="muted small">
                    Citation checks verify the source and exact quote. They do
                    not guarantee the claim is correct.
                  </p>
                </>
              )}
            </article>
            <article className="card">
              <h2>Saved internal notes</h2>
              {ticket?.notes.length ? (
                ticket.notes.map((note) => (
                  <blockquote key={note.id}>{note.content}</blockquote>
                ))
              ) : (
                <p className="muted">
                  No notes saved. Analysis alone never changes the ticket.
                </p>
              )}
            </article>
          </section>
          <aside className="workspace-right">
            <section className="card approval">
              <p className="eyebrow">Human decision</p>
              <h2>Review the exact note.</h2>
              {run?.proposal ? (
                <>
                  <span className="badge">{run.proposal.status}</span>
                  <blockquote>{run.proposal.content}</blockquote>
                  <p className="muted small">
                    Expires{" "}
                    {new Date(run.proposal.expires_at).toLocaleTimeString()}.
                    Applies to ticket version {run.proposal.expected_version}.
                  </p>
                  {run.proposal.status === "pending" ? (
                    <div className="actions">
                      <button
                        disabled={busy}
                        onClick={() => act(() => decide("approve"))}
                      >
                        Approve note
                      </button>
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() => act(() => decide("reject"))}
                      >
                        Reject
                      </button>
                    </div>
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
                <p className="muted">
                  A validated proposal will appear here. You decide whether it
                  becomes an internal note.
                </p>
              )}
              <p className="small muted">
                Approval only saves a sandbox note. It does not replay a
                webhook, rotate a credential, or contact a customer.
              </p>
            </section>
            <section className="card">
              <p className="eyebrow">Audit timeline</p>
              {ticket?.audit.length ? (
                <ol className="timeline">
                  {ticket.audit.map((event, i) => (
                    <li key={i}>
                      <strong>{event.event}</strong>
                      <br />
                      <time>
                        {new Date(event.created_at).toLocaleTimeString()}
                      </time>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="muted small">Decisions will be recorded here.</p>
              )}
            </section>
          </aside>
        </div>
      )}
      <dialog
        ref={dialog}
        aria-labelledby="source-title"
        className="source-drawer"
      >
        <button
          className="secondary close"
          onClick={() => dialog.current?.close()}
          aria-label="Close source"
        >
          Close ×
        </button>
        <p className="eyebrow">Original source · version {source?.version}</p>
        <h2 id="source-title">{source?.title}</h2>
        <h3>{source?.heading}</h3>
        <blockquote>{source?.body}</blockquote>
        <p className="muted small">
          Source: {source?.source_id}. This is the original authorized passage,
          not a generated explanation.
        </p>
      </dialog>
    </>
  );
}
