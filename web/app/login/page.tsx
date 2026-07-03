"use client";
import { useState } from "react";
import { api } from "@/lib/api";

export default function Login() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [err, setErr] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setState("sending");
    const r = await api.requestLink(email.trim().toLowerCase());
    if (r.sent) setState("sent");
    else { setState("error"); setErr(r.error || "Could not send the link."); }
  }

  return (
    <main className="wrap" style={{ maxWidth: 440 }}>
      <h1 className="h1" style={{ marginTop: 24 }}>Sign in</h1>
      <p className="note" style={{ marginBottom: 20 }}>
        Passwordless. Enter your email to receive a one-time sign-in link. Access is limited to approved operators.
      </p>

      {state === "sent" ? (
        <div className="panel">
          <div className="live" style={{ marginBottom: 10 }}>Check your inbox</div>
          <p className="note" style={{ margin: 0 }}>
            If <b>{email}</b> is on the list, a sign-in link is on its way. It expires in 15 minutes.
          </p>
        </div>
      ) : (
        <form className="panel" onSubmit={submit}>
          <div className="field">
            <label>Email</label>
            <input type="email" required value={email} placeholder="you@example.com"
              onChange={(e) => setEmail(e.target.value)} />
          </div>
          <button className="btn" disabled={state === "sending"}>
            {state === "sending" ? "Sending…" : "Email me a link"}
          </button>
          {state === "error" && <p className="note" style={{ color: "var(--bad)", marginTop: 10 }}>{err}</p>}
        </form>
      )}
    </main>
  );
}
