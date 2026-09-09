import Link from "next/link";
export default function Home() {
  return (
    <>
      <section className="hero">
        <p className="eyebrow">Evidence before action</p>
        <h1>
          A useful answer.
          <br />A source you can inspect.
          <br />A decision that stays yours.
        </h1>
        <p className="muted">
          EvidenceDesk reads a support ticket, finds relevant product
          documentation, and proposes an internal note. Nothing is saved to the
          ticket until you approve the exact text.
        </p>
        <div className="actions">
          <Link className="button" href="/workspace">
            Open the workspace →
          </Link>
          <Link className="button secondary" href="/evaluations">
            Inspect evaluation evidence
          </Link>
        </div>
        <span className="badge">
          Anonymous sandbox · Synthetic data · No email sent
        </span>
      </section>
      <section className="grid" aria-label="How it works">
        {[
          [
            "01 / Retrieve",
            "A bounded search",
            "Tenant-scoped lexical and vector search across original RelayNest documentation.",
          ],
          [
            "02 / Inspect",
            "Evidence in plain sight",
            "Read the original excerpts behind each claim. Missing evidence means abstention.",
          ],
          [
            "03 / Decide",
            "Your approval is the boundary",
            "Review an immutable note. Approve once, reject, or leave it pending.",
          ],
        ].map(([step, title, body]) => (
          <article className="card" key={step}>
            <p className="eyebrow">{step}</p>
            <h2>{title}</h2>
            <p className="muted">{body}</p>
          </article>
        ))}
      </section>
    </>
  );
}
