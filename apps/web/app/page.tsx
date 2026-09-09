import Link from "next/link";

const cases = [
  {
    sample: "webhook",
    number: "01",
    title: "Webhook retry failure",
    category: "Delivery",
    body: "The endpoint returned 503. Retries have stopped. Find the safe recovery path.",
  },
  {
    sample: "credential",
    number: "02",
    title: "Expired API credential",
    category: "Access",
    body: "An integration returns credential_expired. Work through a safe credential rotation.",
  },
  {
    sample: "export",
    number: "03",
    title: "Export processing issue",
    category: "Exports",
    body: "An export download link has expired. Check how to make the file available again.",
  },
];

export default function Home() {
  return (
    <div className="home-desk">
      <section className="desk-intro">
        <p className="eyebrow">EvidenceDesk / Support investigations</p>
        <h1>
          Find the answer.
          <br />
          Verify the source.
        </h1>
        <p className="intro-copy">
          Investigate a support ticket, inspect the retrieved passages, and
          decide which internal note is saved.
        </p>
        <div className="actions">
          <Link className="button" href="/workspace?sample=webhook">
            Investigate a sample ticket <span aria-hidden="true">↗</span>
          </Link>
          <Link className="text-link" href="/evaluations">
            See evaluation results
          </Link>
        </div>
        <p className="small muted">
          Synthetic tickets · Your own 24-hour session · No customer messages
        </p>
      </section>
      <section className="case-board" aria-labelledby="cases-title">
        <div className="board-heading">
          <div>
            <p className="eyebrow">Choose a case</p>
            <h2 id="cases-title">Three tickets. One careful decision.</h2>
          </div>
          <span className="badge">RelayNest / Harbor</span>
        </div>
        {cases.map((item) => (
          <Link
            className="case-row"
            href={`/workspace?sample=${item.sample}`}
            key={item.sample}
          >
            <span className="case-number" aria-hidden="true">
              {item.number}
            </span>
            <div>
              <span className="case-category">{item.category}</span>
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </div>
            <span className="case-open">
              Investigate <span aria-hidden="true">↗</span>
            </span>
          </Link>
        ))}
      </section>
      <section className="desk-footnote" aria-label="How investigations work">
        <p>
          <strong>Read. Check. Decide.</strong> Analysis proposes a note. Your
          approval saves the exact text. Inspect every source before deciding.
        </p>
        <a
          className="text-link"
          href="https://github.com/UmitVice/evidencedesk"
        >
          View source code <span aria-hidden="true">↗</span>
        </a>
      </section>
    </div>
  );
}
