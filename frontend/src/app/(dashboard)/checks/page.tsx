"use client";

import { Filter, RefreshCw, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Panel, ToolbarSearch } from "@/components/AppShell";
import { Footer } from "@/components/Footer";
import { api, Paginated } from "@/lib/api";
import { useEnvironment } from "@/lib/environment";
import { formatDate } from "@/lib/format";

type Check = {
  id: string;
  client_name: string;
  type: string;
  status: string;
  outcome: string;
  created_at: string;
  completed_at?: string;
};

export default function ChecksPage() {
  const { env } = useEnvironment();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [data, setData] = useState<Paginated<Check> | null>(null);

  const load = useCallback(() => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
      environment: env,
    });
    if (q.trim().length >= 3) params.set("q", q.trim());
    api<Paginated<Check>>(`/api/checks?${params}`).then(setData).catch(console.error);
  }, [page, pageSize, q, env]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <ToolbarSearch
        value={q}
        onChange={(v) => {
          setPage(1);
          setQ(v);
        }}
        placeholder="Search by client name or check ID (min 3 characters)"
        actions={
          <>
            <button onClick={load} className="grid h-10 w-10 place-items-center rounded-lg border border-[var(--border)] text-[var(--muted)]">
              <RefreshCw size={16} />
            </button>
            <button className="grid h-10 w-10 place-items-center rounded-lg border border-[var(--border)] text-[var(--muted)]">
              <Filter size={16} />
            </button>
            <button className="grid h-10 w-10 place-items-center rounded-lg border border-[var(--border)] text-[var(--muted)]">
              <Upload size={16} />
            </button>
          </>
        }
      />
      <Panel className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-[var(--muted)]">
              <tr className="border-b border-[var(--border)]">
                <th className="px-4 py-3 text-left font-medium">Name</th>
                <th className="px-4 py-3 text-left font-medium">Type</th>
                <th className="px-4 py-3 text-left font-medium">Status</th>
                <th className="px-4 py-3 text-left font-medium">Outcome</th>
                <th className="px-4 py-3 text-left font-medium">Started</th>
                <th className="px-4 py-3 text-left font-medium">Completed</th>
              </tr>
            </thead>
            <tbody>
              {(data?.items || []).map((c) => (
                <tr key={c.id} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-hover)]">
                  <td className="px-4 py-3">{c.client_name}</td>
                  <td className="px-4 py-3">
                    <Badge tone="accent">
                      {c.type === "identity_check" ? "Identity check" : c.type}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge>{c.status === "complete" ? "Complete" : c.status}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={c.outcome === "clear" ? "success" : "warning"}>
                      {c.outcome === "clear" ? "Clear" : "Attention"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-[var(--muted)]">{formatDate(c.created_at)}</td>
                  <td className="px-4 py-3 text-[var(--muted)]">{formatDate(c.completed_at || c.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Footer
          total={data?.total || 0}
          page={page}
          pages={data?.pages || 1}
          pageSize={pageSize}
          onPage={setPage}
          onPageSize={(n) => {
            setPage(1);
            setPageSize(n);
          }}
        />
      </Panel>
    </div>
  );
}
