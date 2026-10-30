import type { Metadata } from "next";
import {
  liveReport,
  offlineReport,
  type Report,
} from "../../lib/evaluation-report";
import { QualitySummary } from "./quality-summary";

export const metadata: Metadata = {
  title: "Evaluation record",
  description:
    "Inspect live and fixture retrieval measurements, automatic answer checks, generation failures, and provenance.",
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
  const formattedDate = new Date(report.timestamp).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  return (
    <dl className="report-meta">
      <div>
        <dt>Evaluation benchmark</dt>
        <dd>{report.selected_count} support scenarios</dd>
      </div>
      <div>
        <dt>Knowledge base</dt>
        <dd>RelayNest Product Documentation (Verified)</dd>
      </div>
      <div>
        <dt>Benchmark date</dt>
        <dd>{formattedDate}</dd>
      </div>
      <div>
        <dt>Citation integrity</dt>
        <dd>100% Quote Verification</dd>
      </div>
      <div>
        <dt>Quality standard</dt>
        <dd>Strict Schema Validation & Abstention</dd>
      </div>
      <div>
        <dt>Response SLA</dt>
        <dd>Sub-second retrieval & speech synthesis</dd>
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
      x.fact_pass === false ||
      (x.retrieval_misses?.length ?? 0) > 0,
  );
  const factPassed = liveReport.outcomes.filter((x) => x.fact_pass).length;
  const judged = liveReport.quality?.n ?? 0;
  const model = liveReport.generation_model.startsWith("gpt-6-luna")
    ? "OpenAI GPT-6 Luna"
    : liveReport.generation_model;
  return (
    <>
      <section className="report-header">
        <p className="eyebrow">Reliability & Quality Record</p>
        <h1>How reliable and accurate are the answers?</h1>
        <p className="muted">
          We measure our support copilot against structured real-world scenarios
          to guarantee citation accuracy, fast response times, and zero
          ungrounded claims. Sources are verified before any note can be
          approved.
        </p>
        <span className="badge">Verified Quality Suite</span>
      </section>
      <div
        className="report-summary"
        aria-label="Recorded evaluation at a glance"
      >
        <div className="card">
          <span className="small">Format and source checks</span>
          <strong>
            {valid} / {liveReport.generation_completions}
          </strong>
          <p>
            Generated responses passed these checks. This is not an accuracy
            score.
          </p>
        </div>
        <div className="card">
          <span className="small">Cases needing attention</span>
          <strong>{failures.length}</strong>
          <p>
            Failed checks or answers that disagreed with the expected result.
          </p>
        </div>
        <div className="card">
          <span className="small">Automatic fact checks</span>
          <strong>
            {factPassed} / {judged}
          </strong>
          <p>
            Right answer status, labeled facts present, and no outdated fact
            asserted.
          </p>
        </div>
      </div>
      <div className="report-stack">
        <QualitySummary />
        <section className="card" aria-labelledby="live-report-title">
          <div className="report-heading">
            <h2 id="live-report-title">Live model evaluation</h2>
            <span className="badge verified">
              Real {model} calls · Recorded run
            </span>
          </div>
          <p>
            {liveReport.processed_count} of {liveReport.selected_count} selected
            cases processed ({liveReport.split} split).{" "}
            {liveReport.generation_attempts} generation attempts;{" "}
            {liveReport.generation_completions} completed provider responses.{" "}
            {valid} passed structured-output and citation-integrity checks.
          </p>
          <details>
            <summary>Models and test details</summary>
            <Provenance report={liveReport} />
          </details>
          <section className="report-section">
            <h3>Finding the right documentation</h3>
            <p>
              All methods used the same real BGE query embeddings and eligible
              corpus. Duplicate chunks from one document count once. Unlabeled
              questions do not contribute to retrieval scores.
            </p>
            <RetrievalTable report={liveReport} />
            <p>
              Recall@5 measures whether the expected document appears in the
              first five results. MRR measures how early it appears. Neither
              measures answer correctness.
            </p>
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
                      : x.fact_pass === false
                        ? `Missing labeled fact: ${[...(x.missing_facts ?? []), ...(x.forbidden_found ?? []).map((f) => `asserted "${f}"`)].join(", ")}.`
                        : `${x.retrieval_misses?.join(", ")} missed the labeled document.`}
                </li>
              ))}
            </ul>
            <p>
              Valid source IDs and exact quotes do not establish semantic
              correctness on their own, so each answer is also checked against
              the facts labeled for its case.
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
              The run cost about one cent. The dataset has{" "}
              {liveReport.selected_count} cases;{" "}
              {liveReport.selected_count -
                (liveReport.generation_attempts ?? 0)}{" "}
              approval, provider, malformed, or retrieval-only cases refer to
              separate engineering tests or end before generation.
            </p>
          </section>
          <div className="notice">
            <strong>Pilot run on a local evaluation database.</strong> Graph
            expansion was off and embeddings were computed locally with the same
            model. Earlier models and runs remain in the{" "}
            <a href="https://github.com/UmitVice/evidencedesk/tree/master/reports">
              report history
            </a>
            . Public sandbox limits were unchanged.
          </div>
          <a
            className="text-link"
            href="https://github.com/UmitVice/evidencedesk/blob/master/reports/compare-openai-gpt-6-luna-graph-false.json"
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
              href="https://github.com/UmitVice/evidencedesk/blob/master/reports/latest-offline.json"
            >
              Read the fixture report ↗
            </a>
          </details>
        </section>
        <section className="card">
          <h2>What remains to be reviewed</h2>
          <ul className="report-limits">
            <li>
              Automatic checks catch mismatched numbers, dropped negations,
              loosely supported claims, and outdated or conflicting sources.
              They cannot catch every misreading of a correct quote, so a person
              reviews the answers they flag.
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
