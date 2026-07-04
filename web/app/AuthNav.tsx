"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function AuthNav() {
  const [email, setEmail] = useState<string | null | undefined>(undefined);
  useEffect(() => { api.me().then((d) => setEmail(d.email)).catch(() => setEmail(null)); }, []);

  if (email === undefined) return <span style={{ width: 60 }} />;
  if (!email) return <Link href="/login" className="signin">Sign in</Link>;
  return (
    <span className="whoami">
      {email.split("@")[0]}
      <button onClick={async () => { await api.logout(); location.reload(); }} title="Sign out" aria-label="Sign out">↪</button>
    </span>
  );
}
