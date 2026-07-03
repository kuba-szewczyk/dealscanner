export default function Help() {
  return (
    <main className="wrap" style={{ maxWidth: 760 }}>
      <h1 className="h1">How the desk works</h1>
      <p className="note" style={{ marginBottom: 24 }}>
        DealScanner is one engine that any investor can point at their own thesis. Two operators
        run on it today — water/wastewater and healthcare — from the same shared database.
      </p>

      <div className="panel" style={{ marginBottom: 14 }}>
        <h2 className="display" style={{ fontSize: 16, margin: "0 0 6px" }}>1 · The database is the brain</h2>
        <p className="note">
          Every listing is scraped once and stored thesis-neutrally — its full text and raw signals.
          A listing is never stored twice: the URL is a hard unique key, so the duplicate pile-ups
          that plagued the old version can&apos;t happen.
        </p>
      </div>

      <div className="panel" style={{ marginBottom: 14 }}>
        <h2 className="display" style={{ fontSize: 16, margin: "0 0 6px" }}>2 · Your settings are the lens</h2>
        <p className="note">
          A cheap global filter drops the obvious non-targets — restaurants, salons — before any AI
          runs. After that, your own thesis (keywords, size band, geography, flags) decides what
          surfaces. Edit it in Thesis setup and the board re-ranks instantly, for free, because it&apos;s
          just re-reading data that&apos;s already there.
        </p>
      </div>

      <div className="panel" style={{ marginBottom: 14 }}>
        <h2 className="display" style={{ fontSize: 16, margin: "0 0 6px" }}>3 · AI where it earns its keep</h2>
        <p className="note">
          Keyword matching is literal and instant. When wording is fuzzy — a &quot;specialty
          contractor&quot; that might be a water business — an optional AI re-judge reads the listing
          and decides, with a reason. Its answers are cached, so you never pay twice for the same call.
        </p>
      </div>

      <div className="panel">
        <h2 className="display" style={{ fontSize: 16, margin: "0 0 6px" }}>4 · Your votes teach it</h2>
        <p className="note">
          Every yes / maybe / no is saved with the full context of the deal at that moment. That&apos;s
          the groundwork for an instinct model that will one day score the way you would — not yet
          built, but collecting from the first vote.
        </p>
      </div>
    </main>
  );
}
