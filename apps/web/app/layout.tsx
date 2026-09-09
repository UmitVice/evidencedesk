import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
export const metadata: Metadata = {
  title: {
    default: "EvidenceDesk | Find the answer. Verify the source.",
    template: "%s | EvidenceDesk",
  },
  description:
    "Investigate a support ticket, inspect the retrieved passages, and decide which internal note is saved.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main-content">
          Skip to content
        </a>
        <header className="site-header">
          <Link className="brand" href="/">
            <span className="brand-mark" aria-hidden="true">
              E
            </span>
            EvidenceDesk
          </Link>
          <nav aria-label="Main navigation">
            <Link href="/workspace">Tickets</Link>
            <Link href="/evaluations">Evaluations</Link>
            <a href="https://github.com/UmitVice/evidencedesk">GitHub</a>
          </nav>
        </header>
        <main id="main-content">{children}</main>
        <footer>
          <p>A support investigation desk for fictional RelayNest tickets.</p>
          <span>Evidence first. Human decision.</span>
        </footer>
      </body>
    </html>
  );
}
