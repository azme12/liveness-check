"use client";

import { KeyRound } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, PageHeader, Panel } from "@/components/AppShell";
import { EnvBanner } from "@/components/EnvBanner";
import { api } from "@/lib/api";
import { useEnvironment } from "@/lib/environment";
import { formatDate } from "@/lib/format";

type ApiKey = {
  id: string;
  access: string;
  kind?: string;
  key: string;
  rate_limit: string;
  created_at: string;
};

export default function ApiKeysPage() {
  const { env, label } = useEnvironment();
  const [items, setItems] = useState<ApiKey[]>([]);
  const [reveal, setReveal] = useState(false);

  const load = useCallback(async () => {
    const data = await api<{ items: ApiKey[] }>(
      `/api/integration/api-keys?environment=${env}`,
    );
    setItems(data.items);
  }, [env]);

  useEffect(() => {
    setReveal(false);
    load().catch(console.error);
  }, [load]);

  async function refresh(id: string) {
    await api(`/api/integration/api-keys/${id}/refresh`, { method: "POST" });
    await load();
    setReveal(true);
  }

  return (
    <div>
      <PageHeader
        title="API keys"
        description={`Server-side secret keys for the ${label} environment. Use sk_* with X-Api-Key on your backend only.`}
      />
      <EnvBanner noun="API keys" />
      <Panel className="mb-4 flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-sm text-[var(--muted)]">
        <span>
          Showing <strong className="text-[var(--text)]">{label}</strong> secret keys (
          {env === "test" ? "sk_test_*" : "sk_live_*"}). Switch TEST/LIVE in the header for the other
          set.
        </span>
        <button
          onClick={() => setReveal((v) => !v)}
          className="rounded-lg bg-[var(--accent)] px-3 py-1.5 font-semibold text-white"
        >
          {reveal ? "Hide keys" : "Reveal keys"}
        </button>
      </Panel>
      <Panel className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-[var(--muted)]">
            <tr className="border-b border-[var(--border)]">
              <th className="px-4 py-3 text-left">Access</th>
              <th className="px-4 py-3 text-left">API key</th>
              <th className="px-4 py-3 text-left">Rate limits</th>
              <th className="px-4 py-3 text-left">Created</th>
              <th className="px-4 py-3 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-[var(--muted)]">
                  No {label.toLowerCase()} API keys yet.
                </td>
              </tr>
            ) : (
              items.map((k) => (
                <tr key={k.id} className="border-b border-[var(--border)] last:border-0">
                  <td className="px-4 py-3">
                    <Badge tone={k.access === "live" ? "live" : "sandbox"}>
                      {k.access === "live" ? "Live" : "Sandbox"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs">
                    {reveal ? k.key : "••••••••••••••••••••••••"}
                  </td>
                  <td className="px-4 py-3 text-[var(--muted)]">{k.rate_limit}</td>
                  <td className="px-4 py-3 text-[var(--muted)]">{formatDate(k.created_at)}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => refresh(k.id)}
                      className="inline-flex items-center gap-1 text-[var(--accent)] hover:underline"
                    >
                      <KeyRound size={14} /> Refresh Key
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
