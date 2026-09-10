import type { Metadata } from "next";
import Link from "next/link";
import { Navigation } from "./navigation";
import "./globals.css";
export const metadata: Metadata = {
  title: {
    default: "EvidenceDesk | AI help for support tickets",
    template: "%s | EvidenceDesk",
  },
  description:
    "Try AI-assisted support with fictional tickets. Check the original sources, then approve or reject a proposed internal note.",
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
          <Navigation />
        </header>
        <main id="main-content">{children}</main>
        <footer>
          <p>Fictional tickets. AI suggestions. Your decision.</p>
          <a href="https://github.com/UmitVice/evidencedesk">
            View on GitHub <span aria-hidden="true">↗</span>
          </a>
        </footer>
      </body>
    </html>
  );
}
