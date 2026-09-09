import { currentReport } from "../../lib/evaluation-report";
export default function Evaluations() {
  const report = currentReport();
  return (
    <>
      <section className="hero">
        <p className="eyebrow">An inspectable engineering record</p>
        <h1>
          What we checked.
          <br />
          What we haven’t.
        </h1>
        <p className="muted">
          A compact regression corpus, not a market benchmark.{" "}
          {report.mode === "live"
            ? "These measurements use the configured live provider. Human answer review remains pending."
            : "These measurements use deterministic test vectors and do not measure live embedding or answer quality."}
        </p>
        <span className="badge">
          {report.mode === "live"
            ? "Live evaluation available — human review pending"
            : "Live evaluation not run"}
        </span>
      </section>
      <section className="card">
        <p className="eyebrow">{report.label}</p>
        <h2>Retrieval comparison</h2>
        <p>
          Document-level Recall@5 and mean reciprocal rank over{" "}
          {report.methods.hybrid.n} answerable labeled cases. Duplicate chunks
          from the same document count once.
        </p>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Method</th>
                <th>Cases</th>
                <th>Recall@5</th>
                <th>MRR</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(report.methods).map(([name, m]) => (
                <tr key={name}>
                  <td>{name}</td>
                  <td>{m.n}</td>
                  <td>{m.recall_at_5?.toFixed(3) ?? "—"}</td>
                  <td>{m.mrr?.toFixed(3) ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="muted">
          No method is required to win. A valid citation and verbatim quote do
          not establish that the associated claim is correct.
        </p>
      </section>
      <section className="grid">
        <article className="card">
          <h2>40 fixed scenarios</h2>
          <p>
            24 development cases. 16 holdout cases. Paraphrases stay in the same
            split.
          </p>
          <p>
            Answerable: 12 · Insufficient: 6 · Obsolete: 4 · Isolation: 4 ·
            Injection: 4 · Malformed: 3 · Provider failure: 2 · Approval: 5.
          </p>
        </article>
        <article className="card">
          <h2>Human review pending</h2>
          <p>
            Review each answer for correctness, completeness, supported
            recommendations, and appropriate abstention. No paid judge or
            keyword score stands in for that review.
          </p>
        </article>
        <article className="card">
          <h2>Known limitations</h2>
          <p>
            Fixture answers only cover supplied samples. Action and failure
            cases are verified separately by engineering tests. No live latency,
            cost, or semantic-quality claim is available.
          </p>
        </article>
      </section>
      <section className="card">
        <h2>Failure and follow-up examples</h2>
        <ul>
          {report.outcomes
            .filter(
              (x) =>
                x.status === "failed" ||
                (x.retrieval_misses?.length ?? 0) > 0 ||
                ("correct_abstention" in x && x.correct_abstention === false),
            )
            .slice(0, 3)
            .map((x) => (
              <li key={x.case_id}>
                {x.case_id}: inspect the fixture response and labeled
                expectation.
              </li>
            ))}
        </ul>
        <p className="muted">
          Full sanitized report, reproduction commands, and test references are
          in the repository.
        </p>
        <a href="https://github.com/UmitVice/evidencedesk/tree/dev/reports">
          Read the reports ↗
        </a>
        <p className="muted">
          Report commit: <code>{report.commit_sha.slice(0, 12)}</code> · Human
          review: {report.human_review}
        </p>
      </section>
    </>
  );
}
