import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";
import AuthNav from "./AuthNav";

export const metadata: Metadata = {
  title: {
    default: "DealScanner — business broker aggregator for searchers",
    template: "%s · DealScanner",
  },
  description:
    "DealScanner aggregates business-for-sale listings from hundreds of brokers into one daily, thesis-filtered feed of acquisition targets — built for search fund leaders, independent sponsors, and self-funded searchers.",
  keywords: [
    "business broker aggregator", "businesses for sale", "search fund", "search fund deal sourcing",
    "independent sponsor", "self-funded search", "acquisition targets", "SMB acquisition",
    "deal sourcing", "proprietary deal flow", "business acquisition",
  ],
  openGraph: {
    title: "DealScanner — business broker aggregator for searchers",
    description:
      "Hundreds of business brokers, aggregated into one daily thesis-filtered feed of acquisition targets. Built for search fund leaders and independent sponsors.",
    type: "website",
    siteName: "DealScanner",
  },
  twitter: {
    card: "summary",
    title: "DealScanner — business broker aggregator for searchers",
    description: "One daily, thesis-filtered feed of business-for-sale listings for searchers and independent sponsors.",
  },
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
              <Link href="/votes">Shortlist</Link>
              <Link href="/settings">Thesis</Link>
              <span className="nav-div" aria-hidden />
              <Link className="nav-util" href="/brokers">Brokers</Link>
              <Link className="nav-util" href="/spend">Spend</Link>
              <Link className="nav-util" href="/help">How it works</Link>
              <Link className="nav-util" href="/build">Build this</Link>
            </nav>
            <AuthNav />
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
