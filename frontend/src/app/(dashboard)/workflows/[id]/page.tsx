"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
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
  const router = useRouter();
  const [wf, setWf] = useState<Workflow | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api<Workflow>(`/api/workflows/${params.id}`)
      .then(setWf)
      .catch(() => router.replace("/workflows"));
  }, [params.id, router]);

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
      router.push(`/workflows/${wf.id}/versions/${created.id}`);
    } catch (err) {
      console.error(err);
      setBusy(false);
    }
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
              <tr
                key={v.id}
                className="cursor-pointer border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-hover)]"
                onClick={() => router.push(`/workflows/${wf.id}/versions/${v.id}`)}
              >
                <td className="px-4 py-3 font-medium">{v.version}</td>
                <td className="px-4 py-3">
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
                </td>
                <td className="px-4 py-3 text-[var(--muted)]">{formatDate(v.updated_at)}</td>
                <td className="px-4 py-3">
                  {v.status === "active" ? (
                    <Badge tone="success">Active</Badge>
                  ) : (
                    <Badge>Inactive</Badge>
                  )}
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
