"use client";

import { ClipboardList, Filter, RefreshCw, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Panel, ToolbarSearch } from "@/components/AppShell";
import { Footer } from "@/components/Footer";
import { api, Paginated } from "@/lib/api";
import { useEnvironment } from "@/lib/environment";

type Session = {
  id: string;
  client_name?: string;
  status?: string;
  created_at?: string;
};

export default function SessionsPage() {
  const { env } = useEnvironment();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [data, setData] = useState<Paginated<Session> | null>(null);

  const load = useCallback(() => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
      environment: env,
    });
    if (q.trim().length >= 3) params.set("q", q.trim());
    api<Paginated<Session>>(`/api/sessions?${params}`).then(setData).catch(console.error);
  }, [page, pageSize, q, env]);

  useEffect(() => {
    load();
  }, [load]);

  const empty = !data?.items?.length;

  return (
    <div>
      <ToolbarSearch
        value={q}
        onChange={(v) => {
          setPage(1);
          setQ(v);
        }}
        placeholder="Search by client name or session ID (min 3 characters)"
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
      <Panel className="min-h-[420px]">
        {empty ? (
          <div className="grid min-h-[420px] place-items-center text-center text-[var(--muted)]">
            <div>
              <ClipboardList className="mx-auto mb-3 opacity-70" size={56} />
              <p>Run clients through workflows to view results.</p>
            </div>
          </div>
        ) : (
          <>
            <table className="w-full text-sm">
              <thead className="text-[var(--muted)]">
                <tr className="border-b border-[var(--border)]">
                  <th className="px-4 py-3 text-left">Session ID</th>
                  <th className="px-4 py-3 text-left">Client</th>
                  <th className="px-4 py-3 text-left">Status</th>
                </tr>
              </thead>
              <tbody>
                {data!.items.map((s) => (
                  <tr key={s.id} className="border-b border-[var(--border)]">
                    <td className="px-4 py-3 font-mono text-xs">{s.id}</td>
                    <td className="px-4 py-3">{s.client_name || "—"}</td>
                    <td className="px-4 py-3">{s.status || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <Footer
              total={data!.total}
              page={page}
              pages={data!.pages}
              pageSize={pageSize}
              onPage={setPage}
              onPageSize={(n) => {
                setPage(1);
                setPageSize(n);
              }}
            />
          </>
        )}
      </Panel>
    </div>
  );
}
