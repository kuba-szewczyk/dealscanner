import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import AuthNav from "./AuthNav";

export const metadata: Metadata = {
  title: "DealScanner — sourcing desk",
  description: "Thesis-agnostic deal-sourcing engine",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-thesis="water">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&family=Space+Grotesk:wght@500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <header className="desk">
          <div className="desk-inner">
            <div>
              <div className="wordmark">DEAL<b>SCANNER</b></div>
              <div className="tag">sourcing desk</div>
            </div>
            <div className="spacer" />
            <nav className="nav">
              <Link href="/">Board</Link>
              <Link href="/settings">Thesis setup</Link>
              <Link href="/brokers">Brokers</Link>
              <Link href="/logs">Logs</Link>
              <Link href="/instinct">Instinct</Link>
              <Link href="/help">How it works</Link>
            </nav>
            <AuthNav />
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
