import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
export const metadata: Metadata = {
  title: "EvidenceDesk | Support with sources",
  description:
    "Inspect the evidence. Approve the action. A bounded support copilot.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <header>
          <Link className="brand" href="/">
            ▧ EvidenceDesk
          </Link>
          <nav aria-label="Main navigation">
            <Link href="/workspace">Workspace</Link>
            <Link href="/evaluations">Evaluations</Link>
            <a href="https://github.com/UmitVice/evidencedesk">Code ↗</a>
          </nav>
        </header>
        <main>{children}</main>
        <footer>
          A fictional product. Real engineering boundaries.{" "}
          <span>Built for inspection.</span>
        </footer>
      </body>
    </html>
  );
}
