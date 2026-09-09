import type { Metadata } from "next";
import {
  liveReport,
  offlineReport,
  type Report,
} from "../../lib/evaluation-report";

export const metadata: Metadata = {
  title: "Evaluation record",
  description:
    "Inspect live and fixture retrieval measurements, generation failures, provenance, and pending human review.",
};
function RetrievalTable({ report }: { report: Report }) {
  return (
    <div
      className="table-scroll"
      tabIndex={0}
      role="region"
      aria-label={`${report.mode} retrieval measurements`}
    >
      <table>
        <caption
          className="small muted"
          style={{ textAlign: "left", paddingBottom: 12 }}
        >
          Document-level retrieval · {report.methods.hybrid.n} labeled
          answerable cases
        </caption>
        <thead>
          <tr>
            <th scope="col">Method</th>
            <th scope="col">Cases</th>
            <th scope="col">Recall@5</th>
            <th scope="col">MRR</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(report.methods).map(([name, m]) => (
            <tr key={name}>
              <th scope="row">{name}</th>
              <td>{m.n}</td>
              <td>{m.recall_at_5?.toFixed(3) ?? "—"}</td>
              <td>{m.mrr?.toFixed(3) ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function Provenance({ report }: { report: Report }) {
  return (
    <dl className="report-meta">
      <div>
        <dt>Generation model</dt>
        <dd>
          <code>{report.generation_model}</code>
        </dd>
      </div>
      <div>
        <dt>Embedding model</dt>
        <dd>
          <code>{report.embedding_manifest.model}</code> ·{" "}
          {report.embedding_manifest.dimension} dimensions
        </dd>
      </div>
      <div>
        <dt>Tested revision</dt>
        <dd>
          <a
            href={`https://github.com/UmitVice/evidencedesk/commit/${report.commit_sha}`}
          >
            <code>{report.commit_sha.slice(0, 12)}</code>
          </a>
        </dd>
      </div>
      <div>
        <dt>Run date / prompt</dt>
        <dd>
          {new Date(report.timestamp).toISOString().slice(0, 10)} ·{" "}
          {report.prompt_version}
        </dd>
      </div>
      <div>
        <dt>Corpus version / hash</dt>
        <dd>
          {report.embedding_manifest.corpus_version} ·{" "}
          <code>{report.corpus_hash.slice(0, 16)}</code>
        </dd>
      </div>
      <div>
        <dt>Dataset hash</dt>
        <dd>
          <code>{report.dataset_hash.slice(0, 16)}</code>
        </dd>
      </div>
    </dl>
  );
}
export default function Evaluations() {
  const valid = liveReport.outcomes.filter(
    (x) => x.schema_valid && x.citation_integrity,
  ).length;
  const failures = liveReport.outcomes.filter(
    (x) =>
      x.status === "failed" ||
      x.correct_abstention === false ||
      (x.retrieval_misses?.length ?? 0) > 0,
  );
  return (
    <>
      <section className="report-header">
        <p className="eyebrow">Evaluation record</p>
        <h1>Evidence about the evidence.</h1>
        <p className="muted">
          Recorded retrieval and generation checks, with failures left visible.
          This is a compact regression corpus, not a market benchmark or a live
          service-health check.
        </p>
        <span className="badge">Human review pending</span>
      </section>
      <div className="report-stack">
        <section className="card" aria-labelledby="live-report-title">
          <div className="report-heading">
            <h2 id="live-report-title">Live model evaluation</h2>
            <span className="badge verified">
              Real Cloudflare calls · Recorded run
            </span>
          </div>
          <p>
            {liveReport.processed_count} of {liveReport.selected_count} selected
            development cases processed. {liveReport.generation_attempts}{" "}
            generation attempts; {liveReport.generation_completions} completed
            provider responses. {valid} passed structured-output and
            citation-integrity checks.
          </p>
          <Provenance report={liveReport} />
          <section className="report-section">
            <h3>Live retrieval comparison</h3>
            <p>
              All methods used the same real BGE query embeddings and eligible
              corpus. Duplicate chunks from one document count once. Unlabeled
              questions do not contribute to retrieval scores.
            </p>
            <RetrievalTable report={liveReport} />
          </section>
          <section className="report-section">
            <h3>Generated-answer failures</h3>
            <ul className="report-failures">
              {failures.map((x) => (
                <li key={x.case_id}>
                  <code>{x.case_id}</code> —{" "}
                  {x.error_code
                    ? `Rejected: ${x.error_code}. No validated answer.`
                    : x.correct_abstention === false
                      ? "Answer status disagreed with the expected abstention."
                      : `${x.retrieval_misses?.join(", ")} missed the labeled document.`}
                </li>
              ))}
            </ul>
            <p>
              Valid source IDs and exact quotes do not establish semantic
              correctness. No human quality score has been assigned.
            </p>
          </section>
          <section className="report-section">
            <h3>Timing and scope</h3>
            <p>
              {liveReport.latency
                ? `Latency n=${liveReport.latency.n}: p50 ${(liveReport.latency.p50_ms / 1000).toFixed(2)} s; p95 ${liveReport.latency.p95_ms === null ? "not estimated" : (liveReport.latency.p95_ms / 1000).toFixed(2) + " s"}. Includes embedding, three retrieval methods, optional generation, and failed cases. These samples describe this run only.`
                : "No measured latency is available."}
            </p>
            <p>
              Exact cost is not reported. The full dataset has 40 cases: 24
              development and 16 holdout. Ten action/provider/malformed cases
              refer to separate engineering tests.
            </p>
          </section>
          {liveReport.prompt_version === "support-v1" && (
            <div className="notice">
              <strong>Historical prompt; follow-up evaluation pending.</strong>{" "}
              This report tested support-v1. The live activation fix uses
              support-v2 and passed hosted answer, abstention, and approval
              checks. Its full quality evaluation remains pending because the
              default daily evaluation-session budget was reached. Earlier
              failures have not been relabeled as successes.
            </div>
          )}
          <a
            className="text-link"
            href="https://github.com/UmitVice/evidencedesk/blob/dev/reports/latest-live.json"
          >
            Read the full live report ↗
          </a>
        </section>
        <section className="card" aria-labelledby="fixture-report-title">
          <div className="report-heading">
            <h2 id="fixture-report-title">
              Fixture / offline engineering evaluation
            </h2>
            <span className="badge">No live model called</span>
          </div>
          <p className="muted">
            Deterministic test vectors measure the fixture retrieval path. These
            numbers are separate from live embedding and generated-answer
            quality.
          </p>
          <RetrievalTable report={offlineReport} />
          <details>
            <summary>Fixture provenance and report</summary>
            <Provenance report={offlineReport} />
            <p className="small muted">
              {offlineReport.processed_count} cases processed; control cases
              retain engineering-test references. No live generation or latency
              is measured.
            </p>
            <a
              className="text-link"
              href="https://github.com/UmitVice/evidencedesk/blob/dev/reports/latest-offline.json"
            >
              Read the fixture report ↗
            </a>
          </details>
        </section>
        <section className="card">
          <h2>What remains to be reviewed</h2>
          <ul className="report-limits">
            <li>
              A human must assess correctness, completeness, supported
              recommendations, and appropriate abstention. Review status remains
              pending.
            </li>
            <li>
              The cosine cutoff is a starting heuristic, not a calibrated
              factuality guarantee. Retrieval can surface passages that do not
              answer the question.
            </li>
            <li>
              Approval, isolation, stale proposals, quotas, and provider
              failures are covered by separate PostgreSQL/API tests. Fixture
              tests are never counted as live model passes.
            </li>
            <li>
              Free-tier limits can make analysis temporarily unavailable. The
              application never substitutes a successful simulated answer for
              failed live inference.
            </li>
          </ul>
        </section>
      </div>
    </>
  );
}
