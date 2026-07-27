"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { BarChart3, Copy, Pencil, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Panel } from "@/components/AppShell";
import { Footer } from "@/components/Footer";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";

type Step = { type: string; label: string };
type Version = {
  id: string;
  version: number;
  description: string;
  status: string;
  steps: Step[];
  updated_at: string;
};
type Workflow = {
  id: string;
  name: string;
  description: string;
  status: string;
  versions: Version[];
};

export default function WorkflowDetailPage() {
  const params = useParams<{ id: string }>();
  const [wf, setWf] = useState<Workflow | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError("");
    api<Workflow>(`/api/workflows/${params.id}`)
      .then((data) => {
        setWf({
          ...data,
          versions: Array.isArray(data.versions) ? data.versions : [],
        });
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load workflow");
      });
  }, [params.id]);

  useEffect(() => {
    load();
  }, [load]);

  async function createVersion() {
    if (!wf) return;
    setBusy(true);
    try {
      const active = wf.versions.find((v) => v.status === "active") || wf.versions[0];
      const created = await api<Version>(`/api/workflows/${wf.id}/versions`, {
        method: "POST",
        body: JSON.stringify({ from_version_id: active?.id }),
      });
      window.location.href = `/workflows/${wf.id}/versions/${created.id}`;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create version");
      setBusy(false);
    }
  }

  if (error && !wf) {
    return (
      <div className="space-y-3">
        <p className="text-[var(--danger)]">{error}</p>
        <a href="/workflows" className="text-sm text-[var(--accent)] underline">
          ← Back to workflows
        </a>
      </div>
    );
  }

  if (!wf) {
    return <div className="text-[var(--muted)]">Loading workflow…</div>;
  }

  return (
    <div>
      <div className="mb-2 text-sm text-[var(--muted)]">
        <Link href="/workflows" className="hover:text-white">
          Workflows
        </Link>
        <span className="mx-2">›</span>
        <span className="text-white">{wf.name}</span>
      </div>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{wf.name}</h1>
          <div className="mt-1 flex items-center gap-2 font-mono text-xs text-[var(--muted)]">
            Workflow template ID: {wf.id}
            <button onClick={() => navigator.clipboard.writeText(wf.id)} className="hover:text-white">
              <Copy size={12} />
            </button>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={createVersion}
            disabled={busy}
            className="inline-flex items-center gap-1 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            <Plus size={16} /> New from template
          </button>
          <button className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] px-3 py-2 text-sm text-[var(--muted)]">
            <BarChart3 size={16} /> Workflow analysis
          </button>
          <Link
            href={
              wf.versions[0]
                ? `/workflows/${wf.id}/versions/${wf.versions[0].id}`
                : `/workflows/${wf.id}`
            }
            className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] px-3 py-2 text-sm text-[var(--muted)] hover:text-white"
          >
            <Pencil size={16} /> Edit
          </Link>
        </div>
      </div>

      <Panel className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-[var(--muted)]">
            <tr className="border-b border-[var(--border)]">
              <th className="px-4 py-3 text-left font-medium">Version</th>
              <th className="px-4 py-3 text-left font-medium">Description</th>
              <th className="px-4 py-3 text-left font-medium">Last updated</th>
              <th className="px-4 py-3 text-left font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {(wf.versions || []).map((v) => (
              <tr key={v.id} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-hover)]">
                <td className="px-4 py-3 font-medium">
                  <a href={`/workflows/${wf.id}/versions/${v.id}`} className="block text-[var(--accent)] underline">
                    {v.version}
                  </a>
                </td>
                <td className="px-4 py-3">
                  <a href={`/workflows/${wf.id}/versions/${v.id}`} className="block">
                    <div className="text-white">{v.description || "—"}</div>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {(v.steps || []).map((s) => (
                        <span
                          key={`${v.id}-${s.type}`}
                          className="rounded-full border border-[var(--accent)]/40 bg-[var(--accent-soft)] px-2 py-0.5 text-[11px] text-[var(--accent)]"
                        >
                          {s.label}
                        </span>
                      ))}
                    </div>
                    <div className="mt-1 font-mono text-[11px] text-[var(--muted)]">ID: {v.id}</div>
                  </a>
                </td>
                <td className="px-4 py-3">
                  <a href={`/workflows/${wf.id}/versions/${v.id}`} className="block text-[var(--muted)]">
                    {formatDate(v.updated_at)}
                  </a>
                </td>
                <td className="px-4 py-3">
                  <a href={`/workflows/${wf.id}/versions/${v.id}`} className="inline-block">
                    {v.status === "active" ? (
                      <Badge tone="success">Active</Badge>
                    ) : (
                      <Badge>Inactive</Badge>
                    )}
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <Footer
          total={(wf.versions || []).length}
          page={1}
          pages={1}
          pageSize={50}
          onPage={() => undefined}
          onPageSize={() => undefined}
        />
      </Panel>
    </div>
  );
}
