"use client";

import { RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, PageHeader, Panel } from "@/components/AppShell";
import { EnvBanner } from "@/components/EnvBanner";
import { Footer } from "@/components/Footer";
import { api, Paginated } from "@/lib/api";
import { formatDate } from "@/lib/format";

type EventRow = {
  id: string;
  event_type?: string;
  type?: string;
  created_at: string;
  attempt?: number;
  status?: string;
  resourceType?: string;
  payload?: Record<string, unknown>;
};

export default function EventsPage() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paginated<EventRow> | null>(null);

  const load = useCallback(() => {
    api<Paginated<EventRow>>(`/api/integration/events?page=${page}&page_size=10`).then(setData).catch(console.error);
  }, [page]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <PageHeader
        title="Events (last 30 days)"
        description="Monitor webhook delivery activity for your integration."
        actions={
          <button onClick={load} className="grid h-10 w-10 place-items-center rounded-lg border border-[var(--border)] text-[var(--muted)]">
            <RefreshCw size={16} />
          </button>
        }
      />
      <EnvBanner noun="events" />
      <Panel className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-[var(--muted)]">
<tr className="border-b border-[var(--border)]">
                <th className="px-4 py-3 text-left">Event type</th>
                <th className="px-4 py-3 text-left">Resource</th>
                <th className="px-4 py-3 text-left">Timestamp</th>
                <th className="px-4 py-3 text-left">Attempt</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">ID</th>
              </tr>
          </thead>
          <tbody>
{(data?.items || []).map((ev) => (
                <tr key={ev.id} className="border-b border-[var(--border)] last:border-0">
                  <td className="px-4 py-3">
                    <Badge tone="accent">{ev.type || ev.event_type}</Badge>
                  </td>
                  <td className="px-4 py-3 text-[var(--muted)]">{ev.resourceType || "—"}</td>
                  <td className="px-4 py-3 text-[var(--muted)]">{formatDate(ev.created_at)}</td>
                  <td className="px-4 py-3">{ev.attempt ?? 1}</td>
                  <td className="px-4 py-3">
                    <Badge tone={ev.status === "succeeded" ? "success" : ev.status === "failed" ? "warning" : "neutral"}>
                      {ev.status === "succeeded" ? "Succeeded" : ev.status || "Pending"}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-[var(--muted)]">{ev.id}</td>
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
