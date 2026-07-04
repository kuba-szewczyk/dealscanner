"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const PRIMARY = [
  ["/", "Deals"], ["/search", "Search"], ["/votes", "Shortlist"], ["/settings", "Thesis"],
];
const UTIL = [
  ["/brokers", "Brokers"], ["/spend", "Spend"], ["/help", "How it works"], ["/build", "Build this"],
];

export default function Nav() {
  const path = usePathname();
  const active = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  return (
    <nav className="nav">
      {PRIMARY.map(([href, label]) => (
        <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}
          className={active(href) ? "nav-on" : ""}>{label}</Link>
      ))}
      <span className="nav-div" aria-hidden />
      {UTIL.map(([href, label]) => (
        <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}
          className={`nav-util${active(href) ? " nav-on" : ""}`}>{label}</Link>
      ))}
    </nav>
  );
}
