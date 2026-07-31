"use client";

import { Badge } from "@/components/AppShell";
import { useEnvironment } from "@/lib/environment";

export function EnvBanner({ noun }: { noun: string }) {
  const { env, label } = useEnvironment();
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-panel)] px-4 py-3 text-sm text-[var(--muted)]">
      <span>
        You are currently viewing {noun} in the <strong className="text-[var(--text)]">{label}</strong>{" "}
        environment.
      </span>
      <Badge tone={env === "live" ? "live" : "sandbox"}>{label}</Badge>
      <span className="text-xs">
        Switch TEST / LIVE in the header to change API keys and environment data.
      </span>
    </div>
  );
}
