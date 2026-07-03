import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import AuthNav from "./AuthNav";

export const metadata: Metadata = {
  title: "DealScanner",
  description: "Thesis-agnostic deal-sourcing platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <header className="desk">
          <div className="desk-inner">
            <div>
              <div className="wordmark">Deal<b>Scanner</b></div>
              <div className="tag-sub">deal sourcing</div>
            </div>
            <div className="spacer" />
            <nav className="nav">
              <Link href="/">Deals</Link>
              <Link href="/search">Search</Link>
              <Link href="/settings">Thesis setup</Link>
              <Link href="/brokers">Brokers</Link>
              <Link href="/activity">Database</Link>
              <Link href="/logs">Activity</Link>
              <Link href="/votes">Voting</Link>
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
