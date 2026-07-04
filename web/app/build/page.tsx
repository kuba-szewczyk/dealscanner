import CopyPrompt from "./CopyPrompt";

export const metadata = { title: "Build this — DealScanner" };

const REPO = "https://github.com/kuba-szewczyk/dealscanner";

const PARTS = [
  { k: "The website", w: "The pages you're looking at now — the board, search, and settings. Built with Next.js and React." },
  { k: "The engine", w: "A small program that visits broker websites every morning and reads their business-for-sale listings." },
  { k: "The AI reader", w: "A cheap AI model (Claude Haiku) that pulls the key facts out of each messy listing — price, revenue, what the business does." },
  { k: "The scorer", w: "Plain rules you control — keywords, deal size, location — that decide which listings match your investment thesis. No AI needed to re-rank." },
  { k: "The database", w: "One simple file (SQLite) that stores every listing once, so nothing is scraped twice." },
  { k: "The daily email", w: "A scheduled job that emails you the new matches each morning, and pings a monitor so you know it ran." },
  { k: "The host", w: "A small $5/month server (Hetzner) with automatic HTTPS. That's the whole running cost." },
];

// A self-sufficient prompt a non-technical user pastes into an AI coding assistant.
const SETUP_PROMPT = `You are helping me set up my own copy of DealScanner, an open-source deal-sourcing web app. I am NOT a developer and I have barely written code, so please guide me one step at a time, explain what each step does in plain language before you do it, and stop to ask me whenever you need something only I can provide (like an email address or an API key). Never paste my secret keys anywhere except my own local .env file.

The project is here: ${REPO}

Please walk me through all of this, checking with me at each stage:

1. TOOLS. Check whether I already have Node.js (version 20+), Python (3.11+), git, and a tool called "uv". For anything I'm missing, give me the simplest install method for my operating system, then wait and confirm it worked before moving on.

2. GET THE CODE. Clone the repository into a sensible folder on my computer and open it.

3. KEYS AND CONFIG. Make a file called .env by copying .env.example, then help me fill it in. For each of these, tell me what it's for, roughly what it costs (they all have free tiers or cost a few cents), and walk me to the exact page to get it:
   - ANTHROPIC_API_KEY — the AI that reads listings (console.anthropic.com)
   - FIRECRAWL_API_KEY — turns broker web pages into clean text (firecrawl.dev)
   - RESEND_API_KEY — sends the daily email (resend.com); or set up a Gmail app password instead
   - DS_SECRET — just generate a random one for me
   - ALLOW_LIST — ask me which email address(es) should be allowed to sign in
   - DIGEST_RECIPIENTS — ask me who should receive the daily deal email

4. START THE BACKEND. Install the engine and API with uv, create the database, and load the two example investment theses.

5. START THE WEBSITE. Install and launch the web app, and start the API. Then tell me the exact address to open in my browser so I can see it running.

6. SEE REAL DATA. Run one scrape and one digest so I can see actual listings show up, and confirm the email works.

7. MAKE IT MINE. Explain, in plain language, how to change what kinds of businesses it looks for by editing the thesis files (keywords, deal size, location). Help me set up my own thesis.

8. (OPTIONAL) RUN IT DAILY ON A SERVER. If I want it running automatically every morning without my laptop on, walk me through the deploy/ folder's runbook one step at a time — renting a small server, locking it down securely, and setting up the daily job. Go slowly and explain the security steps.

Please begin with step 1.`;

export default function BuildPage() {
  return (
    <main className="wrap">
      <h1 className="h1">Build this yourself</h1>
      <p className="sub" style={{ maxWidth: "none", marginBottom: 20 }}>
        DealScanner is open source, and you don&apos;t need to be a developer to run your own copy. The whole thing
        runs on a $5-a-month server. The easiest path is to hand one instruction to an AI coding assistant and answer
        its questions — it does the typing.
      </p>

      <div className="panel" style={{ marginBottom: 16 }}>
        <h2 className="hh2">How it&apos;s built</h2>
        <p className="note" style={{ marginBottom: 4 }}>Seven simple parts, each doing one job:</p>
        <div className="stackgrid">
          {PARTS.map((p) => (
            <div key={p.k} className="stackitem"><b>{p.k}</b><span>{p.w}</span></div>
          ))}
        </div>
      </div>

      <div className="panel highlight" style={{ marginBottom: 16 }}>
        <h2 className="hh2">The easy way: let an AI assistant set it up</h2>
        <ol className="steps">
          <li>
            <b>Get an AI coding assistant.</b> These are apps that can read a project and run the setup for you.
            <a href="https://claude.com/claude-code" target="_blank" rel="noreferrer"> Claude Code</a> is the one this
            project was built with. Install it (or open any coding assistant you already use).
          </li>
          <li>
            <b>Copy the setup prompt below</b> and paste it into the assistant.
          </li>
          <li>
            <b>Answer its questions.</b> It will check what&apos;s on your computer, install anything missing, and ask
            you for a couple of free API keys and your email. It explains every step as it goes — you don&apos;t need
            to know any of the commands.
          </li>
        </ol>
        <CopyPrompt prompt={SETUP_PROMPT} />
      </div>

      <div className="panel">
        <h2 className="hh2">Prefer to do it by hand?</h2>
        <p className="note" style={{ marginBottom: 6 }}>
          If you&apos;re comfortable in a terminal, everything is in the repository: <code className="ic">.env.example</code>
          for configuration, <code className="ic">deploy/README.md</code> for the full server runbook (hardening,
          HTTPS, the daily job), and <code className="ic">thesis/</code> for the investment theses. Changing a
          keyword re-ranks the whole board instantly, and every AI call is metered against a daily cap — a personal
          instance costs cents a day.
        </p>
        <p className="note" style={{ margin: "8px 0 0" }}>
          Source and history: <a href={REPO} target="_blank" rel="noreferrer">{REPO.replace("https://", "")}</a>
        </p>
      </div>
    </main>
  );
}
