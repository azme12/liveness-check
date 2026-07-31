"use client";

import { useEffect, useState } from "react";
import { Badge, PageHeader, Panel } from "@/components/AppShell";
import { EnvBanner } from "@/components/EnvBanner";
import { api } from "@/lib/api";
import { useEnvironment } from "@/lib/environment";

type ApiKey = { key: string };

export default function ApiDocsPage() {
  const { env, label } = useEnvironment();
  const [apiKey, setApiKey] = useState<ApiKey | null>(null);

  useEffect(() => {
    api<{ items: ApiKey[] }>(`/api/integration/api-keys?environment=${env}`)
      .then((data) => setApiKey(data.items[0] || null))
      .catch(console.error);
  }, [env]);

  return (
    <div>
      <PageHeader
        title="API Docs"
        description="One backend serves the dashboard and verification Checks API."
      />
      <EnvBanner noun="API credentials" />
      <Panel className="mb-4 space-y-3 p-5">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">Trustanova Checks API</h2>
          <Badge tone={env === "live" ? "live" : "sandbox"}>{label}</Badge>
        </div>
        <p className="text-sm text-[var(--muted)]">
          Dashboard JWT auth under <code>/api/*</code>. Verification checks under{" "}
          <code>/v1/*</code> with header <code>X-Api-Key</code> using your{" "}
          <strong className="text-[var(--text)]">{label}</strong> secret key.
        </p>
        <div className="rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3 font-mono text-xs text-[var(--muted)]">
          <div>X-Api-Key: {apiKey?.key ? `${apiKey.key.slice(0, 12)}…` : "sk_…"}</div>
        </div>
        <a
          href="http://127.0.0.1:8100/docs"
          target="_blank"
          rel="noreferrer"
          className="inline-block text-[var(--accent)] hover:underline"
        >
          Open Swagger →
        </a>
      </Panel>
    </div>
  );
}
