"use client";
import { useState } from "react";

export default function CopyPrompt({ prompt }: { prompt: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard blocked — fall back to selecting the preview text
      const el = document.getElementById("setup-prompt-text");
      if (el) {
        const r = document.createRange();
        r.selectNodeContents(el);
        const sel = window.getSelection();
        sel?.removeAllRanges();
        sel?.addRange(r);
      }
    }
  }
  return (
    <div className="copyprompt">
      <button className="btn copybtn" onClick={copy}>
        {copied ? "✓ Copied — now paste it into the assistant" : "Copy the setup prompt"}
      </button>
      <details className="promptpreview">
        <summary>Preview the prompt</summary>
        <pre id="setup-prompt-text" className="codeblock"><code>{prompt}</code></pre>
      </details>
    </div>
  );
}
