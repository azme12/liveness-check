"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import { cn } from "@/lib/format";

const SETTINGS_NAV = [
  { href: "/settings/account", label: "Account" },
  { href: "/settings/notifications", label: "Notifications" },
  { href: "/settings/security", label: "Security" },
  { href: "/settings/plan", label: "Plan" },
];

export function SettingsShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 md:flex-row">
      <aside className="w-full shrink-0 md:w-48">
        <h1 className="mb-3 text-xl font-semibold">Settings</h1>
        <nav className="space-y-1">
          {SETTINGS_NAV.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "block rounded-md border px-3 py-2 text-sm transition",
                  active
                    ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]"
                    : "border-transparent text-[var(--muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)]",
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
