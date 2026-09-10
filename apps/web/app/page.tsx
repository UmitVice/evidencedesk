import Link from "next/link";

const cases = [
  {
    sample: "webhook",
    number: "01",
    title: "Webhook retry failure",
    category: "Delivery",
    body: "A delivery failed and retries have stopped. Find out how to recover it.",
  },
  {
    sample: "credential",
    number: "02",
    title: "Expired API credential",
    category: "Access",
    body: "An integration can no longer connect. Check how to replace an expired credential.",
  },
  {
    sample: "export",
    number: "03",
    title: "Expired export link",
    category: "Exports",
    body: "An export download link has expired. Check how to make the file available again.",
  },
];

export default function Home() {
  return (
    <div className="home-desk">
      <section className="desk-intro">
        <p className="eyebrow">
          AI support copilot <span className="badge">Fictional demo</span>
        </p>
        <h1>Turn a support ticket into a reviewed note.</h1>
        <p className="intro-copy">
          EvidenceDesk finds relevant product documentation and uses AI to
          suggest next steps. Check the sources, then decide what to save.
        </p>
        <p className="demo-assurance">
          Nothing is saved as a note without your approval. No customer messages
          are sent.
        </p>
      </section>
      <ol className="journey" aria-label="How to try EvidenceDesk">
        {[
          "Select a sample ticket",
          "Analyze the ticket",
          "Inspect the sources",
          "Approve or reject",
        ].map((step, index) => (
          <li key={step}>
            <span aria-hidden="true">{index + 1}</span>
            {step}
          </li>
        ))}
      </ol>
      <section className="case-board" aria-labelledby="cases-title">
        <div className="board-heading">
          <div>
            <p className="eyebrow">Start here</p>
            <h2 id="cases-title">Select a sample ticket</h2>
          </div>
          <span className="small muted">
            For RelayNest, a fictional software product
          </span>
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
              {item.sample === "webhook" && (
                <span className="recommended">Try this first</span>
              )}
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </div>
            <span className="case-open">
              Open ticket <span aria-hidden="true">→</span>
            </span>
          </Link>
        ))}
      </section>
      <section className="desk-footnote" aria-label="How investigations work">
        <p>
          Sources help you check a suggestion; they do not guarantee it is
          correct.
        </p>
        <Link className="text-link" href="/evaluations">
          See evaluation results <span aria-hidden="true">→</span>
        </Link>
      </section>
    </div>
  );
}
