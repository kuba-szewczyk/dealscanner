export const metadata = { title: "Build this — DealScanner" };

const REPO = "https://github.com/kuba-szewczyk/dealscanner";

const STACK = [
  { k: "Next.js 15 + React 19", w: "The board, search, and this site. Static-rendered, one small bundle." },
  { k: "FastAPI (Python)", w: "A thin JSON layer over the engine — board, search, votes, auth." },
  { k: "SQLite", w: "The whole datastore. One file, zero ops. Listings stored once, deduped by URL." },
  { k: "Claude Haiku", w: "Cheapest capable model — extracts listings from broker pages and judges fuzzy fit." },
  { k: "Firecrawl", w: "Turns messy broker HTML into clean text the model can read." },
  { k: "Resend + Gmail SMTP", w: "The daily digest email (Resend primary, Gmail app-password fallback)." },
  { k: "Caddy", w: "Reverse proxy with automatic HTTPS. The only thing exposed to the internet." },
  { k: "systemd on a Hetzner VPS", w: "Web, API, and the daily scrape timer — restart-on-failure, logs to journald." },
];

function Code({ children }: { children: string }) {
  return <pre className="codeblock"><code>{children}</code></pre>;
}

export default function BuildPage() {
  return (
    <main className="wrap">
      <h1 className="h1">Build this yourself</h1>
      <p className="sub" style={{ maxWidth: "none", marginBottom: 20 }}>
        DealScanner is open source. This page is both a portfolio write-up of how it&apos;s built and a practical
        runbook: clone the repo, point it at your own thesis, and stand it up on your own machine or a small VPS.
        The whole thing runs comfortably on a $5/month box.
      </p>

      <div className="panel" style={{ marginBottom: 16 }}>
        <h2 className="hh2">The stack</h2>
        <div className="stackgrid">
          {STACK.map((s) => (
            <div key={s.k} className="stackitem"><b>{s.k}</b><span>{s.w}</span></div>
          ))}
        </div>
      </div>

      <div className="panel" style={{ marginBottom: 16 }}>
        <h2 className="hh2">Run it locally</h2>
        <p className="note">You need Node 20+, Python 3.11+, and <a href="https://docs.astral.sh/uv/" target="_blank" rel="noreferrer">uv</a>. Then:</p>
        <Code>{`git clone ${REPO}.git
cd dealscanner

# 1. secrets — copy the template and fill in your keys
cp .env.example .env          # ANTHROPIC_API_KEY, FIRECRAWL_API_KEY, mail, ALLOW_LIST…

# 2. engine + API (Python)
cd engine && uv sync --extra api --extra scrape
.venv/bin/dsv2 initdb && .venv/bin/dsv2 seed          # create schema + your theses
.venv/bin/dsv2 scrape-all --fresh && .venv/bin/dsv2 notify

# 3. web (Next.js) — in a second terminal
cd ../web && npm ci && npm run dev                     # board on :3001

# 4. API — in a third terminal
cd ../api && ../engine/.venv/bin/uvicorn main:app --port 8099`}</Code>
      </div>

      <div className="panel" style={{ marginBottom: 16 }}>
        <h2 className="hh2">Make it yours</h2>
        <p className="note" style={{ marginBottom: 6 }}>
          A thesis is a YAML file in <code className="ic">thesis/</code> — keywords, size band, geography, exclusions.
          Copy <code className="ic">water.yaml</code>, edit it, re-seed, and the board re-ranks with no re-scrape.
          Add your own sources on the Brokers page.
        </p>
        <p className="note" style={{ margin: 0 }}>
          Every AI call is metered against a daily cap and uses the cheapest model, so running your own instance
          costs cents a day, not dollars.
        </p>
      </div>

      <div className="panel">
        <h2 className="hh2">Deploy to your own VPS</h2>
        <p className="note">
          The <code className="ic">deploy/</code> folder is a full production kit: a first-login hardening script
          (key-only SSH, firewall, fail2ban, auto-patching), a Caddy config, systemd units for the web + API, and a
          daily scrape timer with a dead-man&apos;s-switch ping. The step-by-step is in <code className="ic">deploy/README.md</code>.
        </p>
        <p className="note" style={{ margin: "8px 0 0" }}>
          Source, issues, and the full history: <a href={REPO} target="_blank" rel="noreferrer">{REPO.replace("https://", "")}</a>
        </p>
      </div>
    </main>
  );
}
