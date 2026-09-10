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

type Operation =
  | "session"
  | "ticket"
  | "analysis"
  | "source"
  | "approve"
  | "reject"
  | "refresh";
type Issue = { message: string; code: string; operation: Operation };
type SourceSelection = { id: string; claim: string; quote: string };
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
      data.error?.message || "The request could not be completed.",
      data.error?.code || "request_failed",
    );
  return data as T;
}
function issueFor(error: unknown, operation: Operation): Issue {
  const code = error instanceof ApiError ? error.code : "connection_failed";
  if (operation === "source" && code === "connection_failed") {
    return {
      code,
      operation,
      message:
        "The source could not be loaded. Check your connection and try again.",
    };
  }
  const messages: Record<string, string> = {
    session_expired:
      "Your demo session has expired. Open a new demo to continue.",
    provider_unavailable:
      "AI analysis is unavailable right now. Please try again later.",
    provider_transient:
      "AI analysis is temporarily unavailable. Please try again later.",
    provider_timeout:
      "The AI service took too long to respond. You can try analyzing again.",
    request_timeout:
      "The request took too long. Refresh the ticket to check its latest state.",
    analysis_failed:
      "The analysis could not produce a usable suggestion. You can try again.",
    provider_invalid:
      "The AI response did not pass the required checks. No note was proposed.",
    invalid_model_output:
      "The AI response did not pass the required checks. No note was proposed.",
    invalid_citation:
      "The AI response did not pass the source checks. No note was proposed.",
    proposal_expired:
      "This draft has expired. Analyze the ticket again for a new draft.",
    proposal_stale:
      "The ticket has changed. Analyze it again before making a decision.",
    connection_failed:
      "We could not confirm the result. Check your connection and refresh the ticket before trying again.",
  };
  return {
    code,
    operation: code === "session_expired" ? "session" : operation,
    message:
      messages[code] ||
      (error instanceof Error
        ? error.message
        : "The request could not be completed."),
  };
}
function requestedSample() {
  const sample = new URLSearchParams(window.location.search).get("sample");
  return sample && ["webhook", "credential", "export"].includes(sample)
    ? sample
    : null;
}
const eventLabels: Record<string, string> = {
  proposed: "Draft proposed",
  applied: "Note approved and saved",
  rejected: "Draft rejected",
};
const sampleLabels: Record<string, string> = {
  webhook: "Webhook retry failure",
  credential: "Expired API credential",
  export: "Expired export link",
};

export default function Workspace() {
  const [tickets, setTickets] = useState<TicketSummary[]>([]);
  const [ticket, setTicket] = useState<TicketResponse | null>(null);
  const [run, setRun] = useState<RunResponse | null>(null);
  const [mode, setMode] = useState<string | null>(null);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<Operation | null>(null);
  const [loading, setLoading] = useState(true);
  const [issue, setIssue] = useState<Issue | null>(null);
  const [ready, setReady] = useState(false);
  const [source, setSource] = useState<SourceResponse | null>(null);
  const [sourceOpen, setSourceOpen] = useState(false);
  const [sourceSelection, setSourceSelection] =
    useState<SourceSelection | null>(null);
  const [expiredId, setExpiredId] = useState<string | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const sourceOpener = useRef<HTMLButtonElement | null>(null);
  const answerHeading = useRef<HTMLHeadingElement>(null);
  const decisionStatus = useRef<HTMLDivElement>(null);
  const operationLock = useRef(false);
  const focusTarget = useRef<"answer" | "decision" | null>(null);
  const generation = useRef(0);
  const opening = useRef<Promise<TicketsResponse> | null>(null);
  const busy = pending !== null;

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
    // Share bootstrap across React's development effect replay; no automatic AI call.
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
          setIssue(issueFor(e, "session"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [restore]);
  useEffect(() => {
    const proposal = run?.proposal;
    if (proposal?.status !== "pending") return;
    const timeout = window.setTimeout(
      () => setExpiredId(proposal.id),
      Math.max(0, new Date(proposal.expires_at).getTime() - Date.now()),
    );
    return () => window.clearTimeout(timeout);
  }, [run?.proposal]);
  useEffect(() => {
    if (pending !== null) return;
    const target =
      focusTarget.current === "answer"
        ? answerHeading.current
        : focusTarget.current === "decision"
          ? decisionStatus.current
          : null;
    if (target) {
      target.focus();
      focusTarget.current = null;
    }
  }, [pending, run]);

  async function act(operation: Operation, task: () => Promise<void>) {
    if (operationLock.current) return;
    operationLock.current = true;
    setPending(operation);
    setIssue(null);
    try {
      await task();
    } catch (error) {
      const next = issueFor(error, operation);
      setIssue(next);
      if (next.code === "session_expired") {
        setReady(false);
        setMode(null);
        setRun(null);
        setTicket(null);
        dialog.current?.close();
      }
    } finally {
      operationLock.current = false;
      setPending(null);
    }
  }
  async function start() {
    await api("sessions", {});
    await restore(await api<TicketsResponse>("tickets"));
  }
  async function refresh() {
    if (ticket) await select(ticket.id);
  }
  async function analyze() {
    if (!ticket) return;
    const previousId = run?.id;
    setRun(null);
    try {
      const result = await api<RunResponse>(`tickets/${ticket.id}/analyze`, {
        question,
      });
      setRun(result);
      focusTarget.current = "answer";
    } finally {
      const detail = await api<TicketResponse>(`tickets/${ticket.id}`);
      setTicket(detail);
      // Do not present an earlier run as the result of a failed new request.
      if (detail.runs[0] && detail.runs[0].id !== previousId)
        setRun(await api<RunResponse>(`runs/${detail.runs[0].id}`));
    }
  }
  async function decide(decision: "approve" | "reject") {
    if (!run?.proposal || !ticket) return;
    await api(`proposals/${run.proposal.id}/decision`, { decision });
    const updatedRun = await api<RunResponse>(`runs/${run.id}`);
    const updatedTicket = await api<TicketResponse>(`tickets/${ticket.id}`);
    setRun(updatedRun);
    setTicket(updatedTicket);
    focusTarget.current = "decision";
  }
  async function inspect(selection: SourceSelection) {
    if (!run) return;
    setSource(null);
    setSourceSelection(selection);
    setSourceOpen(true);
    dialog.current?.showModal();
    setSource(
      await api<SourceResponse>(`runs/${run.id}/sources/${selection.id}`),
    );
  }
  const completedLive = run?.mode === "live" && run.status === "complete";
  const analysisUnavailable =
    issue && ["session", "analysis"].includes(issue.operation);
  const status =
    analysisUnavailable || run?.status === "failed"
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
  const proposal = run?.proposal;
  const stale =
    proposal?.status === "pending" &&
    (proposal.expected_version !== ticket?.version ||
      expiredId === proposal.id ||
      ["proposal_stale", "proposal_expired"].includes(issue?.code || ""));
  const noEvidence = run?.result?.status === "insufficient_evidence";
  const answerReady = run?.status === "complete";
  const decisionIssue =
    issue && ["approve", "reject", "refresh"].includes(issue.operation);
  const sourceIssue = issue?.operation === "source";
  const generalIssue = issue && !decisionIssue && !sourceIssue;
  const proposedStatus = stale
    ? "New analysis needed"
    : proposal?.status === "applied"
      ? "Approved"
      : proposal?.status === "rejected"
        ? "Rejected"
        : "Draft · not saved";

  return (
    <>
      <section className="workspace-title">
        <div>
          <p className="eyebrow">Fictional demo</p>
          <h1>Ticket workspace</h1>
        </div>
        <span
          className={`badge ${completedLive && !analysisUnavailable ? "verified" : ""}`}
          data-testid="analysis-mode"
        >
          {status}
        </span>
      </section>
      <p className="workspace-guidance">
        Analyze a ticket, check the sources, then review the note. Only your
        approval saves it.
      </p>
      {generalIssue && (
        <div className="notice error" role="alert">
          {issue.message}
        </div>
      )}
      {loading ? (
        <div className="card connection-state" role="status">
          <span className="spinner" aria-hidden="true" /> Opening your demo
          tickets…
        </div>
      ) : !ready ? (
        <section className="card session-start">
          <p className="eyebrow">Try a support ticket</p>
          <h2>Your own demo workspace</h2>
          <p>
            Explore three fictional tickets. Check an AI suggestion and decide
            whether to save it as an internal note, visible only in your demo
            session.
          </p>
          <button disabled={busy} onClick={() => act("session", start)}>
            {pending === "session" ? "Opening demo…" : "Open demo workspace"}
          </button>
          <p className="small muted">
            Your session lasts up to 24 hours. AI runs only when you select
            Analyze ticket.
          </p>
          <Link className="text-link" href="/">
            Choose a sample ticket instead
          </Link>
        </section>
      ) : (
        <div className="workspace-grid">
          <div className="workspace-primary">
            <section
              className="card ticket-context"
              aria-labelledby="ticket-heading"
            >
              <div className="section-heading">
                <p className="eyebrow">1 / Select & analyze</p>
                <span className="small muted">Fictional ticket</span>
              </div>
              <label htmlFor="ticket-picker">Sample ticket</label>
              <select
                id="ticket-picker"
                value={ticket?.id || ""}
                disabled={busy}
                onChange={(e) => act("ticket", () => select(e.target.value))}
              >
                {tickets.map((t) => (
                  <option key={t.id} value={t.id}>
                    {sampleLabels[t.sample] || t.title}
                  </option>
                ))}
              </select>
              {pending === "ticket" && (
                <p className="small muted" role="status">
                  Opening selected ticket…
                </p>
              )}
              <div className="ticket-heading">
                <h2 id="ticket-heading">{ticket?.title}</h2>
              </div>
              <p className="ticket-body">{ticket?.body}</p>
              <details className="question-disclosure">
                <summary>
                  Ask a different question{" "}
                  <span className="muted">(optional)</span>
                </summary>
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
                    placeholder="Leave blank to use the ticket question"
                  />
                )}
              </details>
              <div className="analyze-actions">
                <button
                  disabled={busy}
                  onClick={() => act("analysis", analyze)}
                >
                  {pending === "analysis" ? (
                    <>
                      <span className="spinner" aria-hidden="true" /> Analyzing
                      ticket…
                    </>
                  ) : (
                    "Analyze ticket"
                  )}
                </button>
                <p className="small muted">
                  {question
                    ? "Uses your optional question."
                    : "Uses the question above."}{" "}
                  Up to 2 analyses per minute.
                </p>
              </div>
            </section>
            <section
              className="card investigation"
              aria-labelledby="answer-heading"
            >
              <p className="eyebrow">2 / Inspect sources</p>
              <div className="answer-heading">
                <h2 id="answer-heading" ref={answerHeading} tabIndex={-1}>
                  AI suggestion
                </h2>
                {answerReady && (
                  <span className="badge ai-badge">
                    {run.mode === "live" ? "AI generated" : "Simulated result"}
                  </span>
                )}
              </div>
              {pending === "analysis" ? (
                <div className="answer-empty" role="status">
                  <span className="spinner" aria-hidden="true" />
                  <div>
                    <strong>
                      Finding documentation and preparing a suggestion…
                    </strong>
                    <p>
                      You can review the sources and draft when the analysis
                      finishes.
                    </p>
                  </div>
                </div>
              ) : !run ? (
                <div className="answer-empty">
                  <span className="empty-symbol" aria-hidden="true">
                    ↳
                  </span>
                  <div>
                    <strong>
                      {issue?.operation === "analysis"
                        ? "No new suggestion to review"
                        : "Ready when you are"}
                    </strong>
                    <p>
                      Select Analyze ticket to see suggested next steps and
                      their sources.
                    </p>
                  </div>
                </div>
              ) : run.status === "failed" ? (
                <div className="notice error" role="alert">
                  This analysis could not produce a usable suggestion. No note
                  was proposed. Try analyzing again.
                  <details>
                    <summary>Error details</summary>
                    <code>{run.error_code}</code>
                  </details>
                </div>
              ) : run.status === "running" ? (
                <div className="notice">
                  <p>
                    This analysis has not finished. Check its saved status
                    before starting another.
                  </p>
                  <button
                    className="secondary"
                    disabled={busy}
                    onClick={() => act("refresh", refresh)}
                  >
                    Refresh ticket
                  </button>
                </div>
              ) : noEvidence ? (
                <div className="notice abstention">
                  <h3>Not enough evidence</h3>
                  <p>
                    The available documentation does not support an answer. No
                    note is proposed. Get a product expert’s clarification
                    before proceeding.
                  </p>
                  <p className="small">
                    You can choose another ticket or ask a different question
                    above.
                  </p>
                </div>
              ) : (
                <>
                  <p className="small muted">
                    Open a source to compare the original text with each
                    suggestion. Sources do not guarantee correctness.
                  </p>
                  {run.result?.claims.map((claim, i) => (
                    <div className="claim" key={i}>
                      <span className="claim-number">Suggestion {i + 1}</span>
                      <p>{claim.text}</p>
                      <div className="claim-sources">
                        {claim.citations.map((citation, j) => {
                          const title = run.evidence.find(
                            (item) => item.id === citation.source_id,
                          )?.title;
                          return (
                            <button
                              key={j}
                              aria-disabled={busy}
                              className="source-link secondary"
                              onClick={(event) => {
                                if (operationLock.current) return;
                                sourceOpener.current = event.currentTarget;
                                act("source", () =>
                                  inspect({
                                    id: citation.source_id,
                                    claim: claim.text,
                                    quote: citation.quote,
                                  }),
                                );
                              }}
                            >
                              <span className="source-icon" aria-hidden="true">
                                ≡
                              </span>
                              <span>
                                View source {i + 1}.{j + 1}
                                {title && (
                                  <span className="source-button-title">
                                    {title}
                                  </span>
                                )}
                              </span>
                              <span aria-hidden="true">→</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                  {proposal?.status === "pending" && (
                    <div className="answer-next">
                      <span className="small muted">
                        After checking the sources
                      </span>
                      <a className="text-link" href="#proposal-title">
                        Review the proposed note{" "}
                        <span aria-hidden="true">→</span>
                      </a>
                    </div>
                  )}
                </>
              )}
              {sourceIssue && !sourceOpen && (
                <p className="notice error" role="alert">
                  {issue.message} Open the source to try again.
                </p>
              )}
            </section>
          </div>
          <aside
            className="workspace-right"
            aria-label="Review and saved notes"
          >
            <section className="card approval" aria-labelledby="proposal-title">
              <p className="eyebrow">3 / Your decision</p>
              <h2 id="proposal-title" tabIndex={-1}>
                Review the internal note
              </h2>
              {proposal ? (
                <>
                  <span
                    className={`badge ${proposal.status === "applied" ? "verified" : "ai-badge"}`}
                  >
                    {proposedStatus}
                  </span>
                  {proposal.status !== "applied" && (
                    <blockquote className="proposed-note">
                      {proposal.content}
                    </blockquote>
                  )}
                  {decisionIssue && (
                    <div className="notice error" role="alert">
                      <p>{issue.message}</p>
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() => act("refresh", refresh)}
                      >
                        Refresh ticket
                      </button>
                    </div>
                  )}
                  {proposal.status === "pending" ? (
                    stale ? (
                      <div className="notice">
                        <p>
                          This draft has expired or the ticket has changed.
                          Analyze the ticket again before deciding.
                        </p>
                        <a className="text-link" href="#ticket-heading">
                          Back to analysis ↑
                        </a>
                      </div>
                    ) : (
                      <>
                        <p className="small muted">
                          Approval saves this exact text as an internal note in
                          your demo session. It does not send a reply or fix the
                          issue.
                        </p>
                        <div className="decision-actions">
                          <button
                            disabled={busy}
                            onClick={() =>
                              act("approve", () => decide("approve"))
                            }
                          >
                            {pending === "approve"
                              ? "Saving approved note…"
                              : "Approve & save note"}
                          </button>
                          <button
                            className="secondary"
                            disabled={busy}
                            onClick={() =>
                              act("reject", () => decide("reject"))
                            }
                          >
                            {pending === "reject"
                              ? "Rejecting draft…"
                              : "Reject draft"}
                          </button>
                        </div>
                        <p className="small muted">
                          Rejecting saves no note. You can analyze again.
                        </p>
                        <details className="technical-details">
                          <summary>Draft details</summary>
                          <p className="small muted">
                            For ticket version {proposal.expected_version}.
                            Expires{" "}
                            {new Date(proposal.expires_at).toLocaleString(
                              "en-US",
                            )}
                            .
                          </p>
                          <span className="small muted">
                            Content fingerprint
                          </span>
                          <code className="hash">{proposal.content_hash}</code>
                        </details>
                      </>
                    )
                  ) : (
                    <div
                      className={`decision-result ${proposal.status === "applied" ? "success" : ""}`}
                      role="status"
                      tabIndex={-1}
                      ref={decisionStatus}
                    >
                      <strong>
                        {proposal.status === "applied"
                          ? "Note approved and saved"
                          : "Draft rejected. No note saved."}
                      </strong>
                      <p>
                        {proposal.status === "applied"
                          ? "The exact text is in Saved internal notes below."
                          : "You can analyze again or try another sample ticket."}
                      </p>
                      <Link className="text-link" href="/">
                        Try another sample ticket →
                      </Link>
                    </div>
                  )}
                </>
              ) : (
                <div className="proposal-empty">
                  <strong>
                    {noEvidence
                      ? "No draft to approve"
                      : pending === "analysis"
                        ? "Preparing a draft…"
                        : "Your review comes next"}
                  </strong>
                  <p className="small muted">
                    {noEvidence
                      ? "There isn’t enough evidence to propose a note."
                      : "After analysis, compare the proposed note with the sources. Approve it to save, or reject it."}
                  </p>
                </div>
              )}
            </section>
            <section
              className="card saved-notes"
              aria-labelledby="saved-notes-title"
            >
              <div className="section-heading">
                <h2 id="saved-notes-title">Saved internal notes</h2>
                <span
                  className="note-count"
                  aria-label={`${ticket?.notes.length ?? 0} saved notes`}
                >
                  {ticket?.notes.length ?? 0}
                </span>
              </div>
              {ticket?.notes.length ? (
                ticket.notes.map((note) => (
                  <div className="saved-note" key={note.id}>
                    <span className="badge verified">
                      Saved after your approval
                    </span>
                    <blockquote>{note.content}</blockquote>
                    <time className="small muted" dateTime={note.created_at}>
                      {new Date(note.created_at).toLocaleString("en-US")}
                    </time>
                  </div>
                ))
              ) : (
                <p className="small muted">
                  No saved notes yet. AI suggestions stay separate until you
                  approve them.
                </p>
              )}
              <details className="activity">
                <summary>Decision history</summary>
                {ticket?.audit.length ? (
                  <ol className="timeline">
                    {ticket.audit.map((event, i) => (
                      <li key={i}>
                        <strong>
                          {eventLabels[event.event] || event.event}
                        </strong>
                        <time dateTime={event.created_at}>
                          {new Date(event.created_at).toLocaleString("en-US")}
                        </time>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="small muted">
                    Drafts and your decisions will appear here.
                  </p>
                )}
              </details>
            </section>
          </aside>
        </div>
      )}
      <dialog
        ref={dialog}
        onKeyDown={(event) => {
          if (event.key !== "Tab") return;
          const controls = Array.from(
            event.currentTarget.querySelectorAll<HTMLElement>(
              "button:not([disabled]), summary, a[href]",
            ),
          ).filter((element) => element.getClientRects().length > 0);
          const first = controls[0];
          const last = controls.at(-1);
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last?.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first?.focus();
          }
        }}
        onClose={() => {
          setSourceOpen(false);
          sourceOpener.current?.focus();
        }}
        aria-labelledby="source-title"
        className="source-drawer"
      >
        <div className="source-drawer-header">
          <span className="eyebrow">Original source</span>
          <button
            className="secondary"
            onClick={() => dialog.current?.close()}
            aria-label="Close source"
          >
            Close <span aria-hidden="true">×</span>
          </button>
        </div>
        <h2 id="source-title">{source?.title || "Source evidence"}</h2>
        {pending === "source" ? (
          <p role="status" className="connection-state">
            <span className="spinner" aria-hidden="true" /> Loading the original
            passage…
          </p>
        ) : sourceIssue ? (
          <div className="notice error" role="alert">
            <p>{issue.message}</p>
            <button
              className="secondary"
              onClick={() =>
                sourceSelection && act("source", () => inspect(sourceSelection))
              }
            >
              Try loading source again
            </button>
          </div>
        ) : (
          source && (
            <>
              <p className="small muted">
                Product documentation captured for this analysis. Compare it
                with the AI suggestion before deciding.
              </p>
              <section className="claim-context">
                <h3>AI suggestion under review</h3>
                <p>{sourceSelection?.claim}</p>
              </section>
              <h3>Original excerpt</h3>
              <blockquote className="exact-quote">
                {sourceSelection?.quote}
              </blockquote>
              <details open>
                <summary>Full passage · {source.heading}</summary>
                <p className="source-passage">{source.body}</p>
              </details>
              <p className="small muted integrity-note">
                An exact quote can still be misinterpreted. Check whether it
                supports the suggestion.
              </p>
              <details className="technical-details">
                <summary>Source details</summary>
                <p className="small muted">
                  Source: {source.source_id} · Version {source.version}
                  {source.status ? ` · ${source.status}` : ""}
                </p>
              </details>
            </>
          )
        )}
      </dialog>
    </>
  );
}
