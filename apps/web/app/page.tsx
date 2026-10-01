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
          AI Support Copilot <span className="badge">Verified Citations</span>
        </p>
        <h1>Resolve support tickets with verified AI & voice notes.</h1>
        <p className="intro-copy">
          EvidenceDesk instantly retrieves authorized product documentation and
          proposes structured, citation-backed solutions. Support teams can type
          or speak to investigate issues, inspect original excerpts, and approve
          internal resolution notes after reviewing the evidence.
        </p>
        <p className="demo-assurance">
          Safe & controlled: No internal note is saved without your explicit
          approval, and no customer messages are sent automatically.
        </p>
      </section>
      <ol className="journey" aria-label="How to try EvidenceDesk">
        {[
          "Select a support ticket",
          "Analyze a typed or recorded question",
          "Inspect verified sources",
          "Approve & save note",
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
            <p className="eyebrow">Interactive Cases</p>
            <h2 id="cases-title">Select a support ticket</h2>
          </div>
          <span className="small muted">
            Real-world SaaS support scenarios with verified documentation
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
                <span className="recommended">Recommended first</span>
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
          Every recommendation links directly to verified documentation so you
          can always check the original source before saving.
        </p>
        <Link className="text-link" href="/evaluations">
          View accuracy & reliability benchmarks{" "}
          <span aria-hidden="true">→</span>
        </Link>
      </section>
    </div>
  );
}
