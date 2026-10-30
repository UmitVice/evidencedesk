"use client";
import { useEffect, useState } from "react";
import type { QualitySummaryResponse } from "../../lib/api-contract";

const labels: Record<string, string> = {
  number_mismatch: "Number not in its quote",
  negation_dropped: "Negation dropped",
  weak_quote_support: "Claim loosely supported",
  note_adds_number: "Note adds a number",
  outdated_source: "Outdated source cited",
  conflicting_sources: "Conflicting sources cited",
  weak_retrieval: "Weak retrieval match",
  fallback_model: "Fallback model used",
};

// Counts only: the API never returns ticket text or answers for this view.
export function QualitySummary() {
  const [data, setData] = useState<QualitySummaryResponse | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    fetch("/api/quality/summary", { cache: "no-store" })
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((summary: QualitySummaryResponse) => active && setData(summary))
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
    };
  }, []);
  return (
    <section className="card" aria-labelledby="production-checks-title">
      <div className="report-heading">
        <h2 id="production-checks-title">Production answer checks</h2>
        <span className="badge verified">Last 7 days · Live</span>
      </div>
      <p className="muted">
        Every live answer passes automatic checks: numbers and negations must
        match their quotes, claims must share wording with their sources, the
        note may not add numbers, and outdated, conflicting, or weakly matched
        sources are flagged. A person reviews only flagged answers.
      </p>
      {failed ? (
        <p className="small muted">
          The live summary is unavailable right now. The API may be waking up;
          reload in a minute.
        </p>
      ) : !data ? (
        <p className="small muted" role="status">
          Loading live counts…
        </p>
      ) : (
        <>
          <div className="report-summary" aria-label="Production answer checks">
            <div className="card">
              <span className="small">Live answers</span>
              <strong>{data.complete}</strong>
              <p>Completed analyses in the last {data.days} days.</p>
            </div>
            <div className="card">
              <span className="small">Flagged for review</span>
              <strong>{data.flagged}</strong>
              <p>Answers with at least one review-level flag.</p>
            </div>
            <div className="card">
              <span className="small">Failed safely</span>
              <strong>{data.failed}</strong>
              <p>Analyses that produced no answer, for example a timeout.</p>
            </div>
          </div>
          {data.flags.length > 0 && (
            <ul className="report-limits">
              {data.flags.map((flag) => (
                <li key={flag.code}>
                  {labels[flag.code] ?? flag.code}: {flag.count}
                </li>
              ))}
            </ul>
          )}
          {data.models.length > 0 && (
            <p className="small muted">
              Answered by:{" "}
              {data.models
                .map((model) => `${model.model} (${model.count})`)
                .join(", ")}
              .
            </p>
          )}
        </>
      )}
    </section>
  );
}
