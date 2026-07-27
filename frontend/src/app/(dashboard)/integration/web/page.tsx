"use client";

import { Copy, KeyRound } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, PageHeader, Panel } from "@/components/AppShell";
import { EnvBanner } from "@/components/EnvBanner";
import { api } from "@/lib/api";
import { useEnvironment } from "@/lib/environment";

type SdkResponse = {
  environment: string;
  api_key?: { key: string; id: string } | null;
  web_sdk_key?: { key: string; id: string } | null;
  snippet: string;
  notes: { api: string; web_sdk: string };
};

export default function WebSdkPage() {
  const { env, label } = useEnvironment();
  const [data, setData] = useState<SdkResponse | null>(null);
  const [reveal, setReveal] = useState(false);
  const [copied, setCopied] = useState("");

  const load = useCallback(() => {
    api<SdkResponse>(`/api/integration/sdk?environment=${env}`)
      .then(setData)
      .catch(console.error);
  }, [env]);

  useEffect(() => {
    setReveal(false);
    load();
  }, [load]);

  async function refreshWebKey() {
    if (!data?.web_sdk_key?.id) return;
    await api(`/api/integration/api-keys/${data.web_sdk_key.id}/refresh`, { method: "POST" });
    load();
    setReveal(true);
  }

  async function copy(text: string, labelKey: string) {
    await navigator.clipboard.writeText(text);
    setCopied(labelKey);
    setTimeout(() => setCopied(""), 1500);
  }

  const pk = data?.web_sdk_key?.key || "";
  const sk = data?.api_key?.key || "";

  return (
    <div>
      <PageHeader
        title="Web SDK"
        description={`Browser SDK credentials for the ${label} environment. Use the public pk_* key in your frontend.`}
      />
      <EnvBanner noun="Web SDK credentials" />

      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <Panel className="p-5">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="font-semibold">Publishable key (Web SDK)</h2>
            <Badge tone={env === "live" ? "live" : "sandbox"}>{label}</Badge>
          </div>
          <p className="mb-3 text-sm text-[var(--muted)]">{data?.notes.web_sdk}</p>
          <code className="block break-all rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 font-mono text-xs">
            {reveal ? pk || "—" : "pk_••••••••••••••••••••"}
          </code>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setReveal((v) => !v)}
              className="rounded-lg bg-[var(--accent)] px-3 py-1.5 text-sm font-semibold text-white"
            >
              {reveal ? "Hide" : "Reveal"}
            </button>
            <button
              type="button"
              onClick={() => pk && copy(pk, "pk")}
              className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--muted)]"
            >
              <Copy size={14} /> {copied === "pk" ? "Copied" : "Copy"}
            </button>
            <button
              type="button"
              onClick={refreshWebKey}
              className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--accent)]"
            >
              <KeyRound size={14} /> Refresh
            </button>
          </div>
        </Panel>

        <Panel className="p-5">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h2 className="font-semibold">Secret API key (server)</h2>
            <Badge tone={env === "live" ? "live" : "sandbox"}>{label}</Badge>
          </div>
          <p className="mb-3 text-sm text-[var(--muted)]">{data?.notes.api}</p>
          <code className="block break-all rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 font-mono text-xs">
            {reveal ? sk || "—" : "sk_••••••••••••••••••••"}
          </code>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => sk && copy(sk, "sk")}
              className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm text-[var(--muted)]"
            >
              <Copy size={14} /> {copied === "sk" ? "Copied" : "Copy"}
            </button>
            <a href="/integration/api-keys" className="text-sm text-[var(--accent)] hover:underline">
              Manage API keys →
            </a>
          </div>
        </Panel>
      </div>

      <Panel className="p-5">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold">Install snippet ({label})</h2>
          <button
            type="button"
            onClick={() => data?.snippet && copy(data.snippet, "snip")}
            className="inline-flex items-center gap-1 text-sm text-[var(--accent)]"
          >
            <Copy size={14} /> {copied === "snip" ? "Copied" : "Copy"}
          </button>
        </div>
        <pre className="overflow-x-auto rounded-lg border border-[var(--border)] bg-[var(--bg)] p-4 text-xs leading-relaxed text-[var(--muted)]">
          {data?.snippet || "Loading…"}
        </pre>
      </Panel>
    </div>
  );
}
