"use client";

import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import {
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PageHeader, Panel } from "@/components/AppShell";
import { EnvBanner } from "@/components/EnvBanner";
import { Footer } from "@/components/Footer";
import { api } from "@/lib/api";
import { cn, formatDate } from "@/lib/format";

type LogsResponse = {
  items: Array<{
    id: string;
    method: string;
    path: string;
    status_code: number;
    created_at: string;
  }>;
  total: number;
  page: number;
  pages: number;
  series: Array<{ label: string; count: number }>;
};

export default function LogsPage() {
  const [methods, setMethods] = useState({ POST: true, GET: true, DELETE: true });
  const [onlyErrors, setOnlyErrors] = useState(false);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<LogsResponse | null>(null);

  async function load(p = page) {
    const selected = Object.entries(methods)
      .filter(([, on]) => on)
      .map(([m]) => m)
      .join(",");
    const qs = new URLSearchParams({
      methods: selected || "POST",
      only_errors: String(onlyErrors),
      page: String(p),
      page_size: "20",
    });
    const res = await api<LogsResponse>(`/api/integration/logs?${qs}`);
    setData(res);
  }

  useEffect(() => {
    load().catch(console.error);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [methods, onlyErrors, page]);

  return (
    <div>
      <PageHeader
        title="Logs (last 90 days)"
        description="Track and review all API calls to LivenCube to monitor and optimize your Integration."
      />
      <EnvBanner noun="logs" />
      <Panel className="mb-4 p-4">
        <div className="mb-3 text-sm font-medium">API activity</div>
        <div className="h-40">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data?.series || []}>
              <XAxis dataKey="label" hide />
              <YAxis hide />
              <Tooltip contentStyle={{ background: "#1a1d24", border: "1px solid #2a2f3a" }} />
              <Area type="monotone" dataKey="count" stroke="#9aa3b2" fill="#2a2f3a" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Panel>
      <div className="mb-3 flex flex-wrap items-center gap-4 text-sm">
        {(["POST", "GET", "DELETE"] as const).map((m) => (
          <label key={m} className="inline-flex items-center gap-2 text-[var(--muted)]">
            <input
              type="checkbox"
              checked={methods[m]}
              onChange={(e) => {
                setPage(1);
                setMethods((prev) => ({ ...prev, [m]: e.target.checked }));
              }}
            />
            {m}
          </label>
        ))}
        <label className="inline-flex items-center gap-2 text-[var(--muted)]">
          <input
            type="checkbox"
            checked={onlyErrors}
            onChange={(e) => {
              setPage(1);
              setOnlyErrors(e.target.checked);
            }}
          />
          ONLY ERRORS
        </label>
        <button onClick={() => load()} className="ml-auto grid h-9 w-9 place-items-center rounded-lg border border-[var(--border)] text-[var(--muted)]">
          <RefreshCw size={16} />
        </button>
      </div>
      <Panel className="overflow-hidden">
        <ul className="divide-y divide-[var(--border)]">
          {(data?.items || []).map((log) => (
            <li key={log.id} className="flex items-center gap-3 px-4 py-3 text-sm">
              <span
                className={cn(
                  "h-2.5 w-2.5 rounded-full",
                  log.status_code >= 400 ? "bg-[var(--danger)]" : "bg-[var(--success)]",
                )}
              />
              <span className="w-16 font-semibold text-[var(--accent)]">{log.method}</span>
              <span className="flex-1 font-mono text-xs text-[var(--muted)]">{log.path}</span>
              <span className="text-[var(--muted)]">{log.status_code}</span>
              <span className="text-[var(--muted)]">{formatDate(log.created_at)}</span>
            </li>
          ))}
        </ul>
        <Footer
          total={data?.total || 0}
          page={page}
          pages={data?.pages || 1}
          pageSize={20}
          onPage={setPage}
          onPageSize={() => undefined}
        />
      </Panel>
    </div>
  );
}
