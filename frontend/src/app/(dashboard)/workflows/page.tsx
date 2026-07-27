"use client";

import Link from "next/link";
import { Copy, Filter, Plus, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Panel, ToolbarSearch } from "@/components/AppShell";
import { Footer } from "@/components/Footer";
import { api, Paginated } from "@/lib/api";
import { useEnvironment } from "@/lib/environment";
import { formatDate } from "@/lib/format";

type Workflow = {
  id: string;
  name: string;
  description: string;
  status: string;
  updated_at: string;
};

export default function WorkflowsPage() {
  const { env } = useEnvironment();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paginated<Workflow> | null>(null);

  const load = useCallback(() => {
    const params = new URLSearchParams({ page: String(page), page_size: "10", environment: env });
    if (q.trim().length >= 3) params.set("q", q.trim());
    api<Paginated<Workflow>>(`/api/workflows?${params}`).then(setData).catch(console.error);
  }, [page, q, env]);

  useEffect(() => {
    load();
  }, [load]);

  async function createWorkflow() {
    const name = window.prompt("Workflow name", "New workflow");
    if (!name) return;
    await api("/api/workflows", {
      method: "POST",
      body: JSON.stringify({ name, description: "", steps: [{ type: "identity_check", label: "Identity Check" }] }),
    });
    load();
  }

  return (
    <div>
      <ToolbarSearch
        value={q}
        onChange={(v) => {
          setPage(1);
          setQ(v);
        }}
        placeholder="Search by template name or ID (min 3 characters)"
        actions={
          <>
            <button onClick={load} className="grid h-10 w-10 place-items-center rounded-lg border border-[var(--border)] text-[var(--muted)]">
              <RefreshCw size={16} />
            </button>
            <button className="grid h-10 w-10 place-items-center rounded-lg border border-[var(--border)] text-[var(--muted)]">
              <Filter size={16} />
            </button>
            <button
              onClick={createWorkflow}
              className="inline-flex items-center gap-1 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-semibold text-white"
            >
              <Plus size={16} /> New workflow
            </button>
          </>
        }
      />
      <Panel className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-[var(--muted)]">
            <tr className="border-b border-[var(--border)]">
              <th className="px-4 py-3 text-left font-medium">Workflow name</th>
              <th className="px-4 py-3 text-left font-medium">Description</th>
              <th className="px-4 py-3 text-left font-medium">Status</th>
              <th className="px-4 py-3 text-left font-medium">Last updated</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items || []).map((w) => (
              <tr key={w.id} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-hover)]">
                <td className="px-4 py-3">
                  <Link href={`/workflows/${w.id}`} className="font-medium text-white hover:text-[var(--accent)]">
                    {w.name}
                  </Link>
                  <div className="mt-1 flex items-center gap-1 font-mono text-xs text-[var(--muted)]">
                    {w.id}
                    <button
                      onClick={() => navigator.clipboard.writeText(w.id)}
                      className="hover:text-white"
                      title="Copy ID"
                    >
                      <Copy size={12} />
                    </button>
                  </div>
                </td>
                <td className="px-4 py-3 text-[var(--muted)]">{w.description || "—"}</td>
                <td className="px-4 py-3">
                  <Badge tone="success">{w.status === "active" ? "Active" : w.status}</Badge>
                </td>
                <td className="px-4 py-3 text-[var(--muted)]">{formatDate(w.updated_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <Footer
          total={data?.total || 0}
          page={page}
          pages={data?.pages || 1}
          pageSize={10}
          onPage={setPage}
          onPageSize={() => undefined}
        />
      </Panel>
    </div>
  );
}
