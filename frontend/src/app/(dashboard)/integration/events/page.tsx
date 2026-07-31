"use client";

import { RefreshCw } from "lucide-react";
import { Fragment, useCallback, useEffect, useState } from "react";
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
  payload?: {
    scores?: Record<string, unknown>;
    outcome?: string;
    type?: string;
    summary?: { outcome?: string };
    checks?: Array<{ type?: string; outcome?: string; scores?: Record<string, unknown> }>;
  };
};

function scoreLine(payload: EventRow["payload"]) {
  const scores = payload?.scores;
  if (!scores) return "—";
  const parts: string[] = [];
  if (typeof scores.face_match_score === "number") parts.push(`match ${scores.face_match_score.toFixed(2)}`);
  if (typeof scores.liveness_score === "number") parts.push(`live ${scores.liveness_score.toFixed(2)}`);
  if (typeof scores.document_quality === "number") parts.push(`doc ${scores.document_quality.toFixed(2)}`);
  return parts.length ? parts.join(" · ") : "—";
}

export default function EventsPage() {
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paginated<EventRow> | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

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
        description="Webhook deliveries with verification scores (face match, liveness, document quality)."
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
              <th className="px-4 py-3 text-left">Outcome</th>
              <th className="px-4 py-3 text-left">Scores</th>
              <th className="px-4 py-3 text-left">Timestamp</th>
              <th className="px-4 py-3 text-left">Status</th>
              <th className="px-4 py-3 text-left">Payload</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items || []).map((ev) => {
              const payload = ev.payload;
              const outcome =
                payload?.outcome || payload?.summary?.outcome || payload?.checks?.[0]?.outcome || "—";
              return (
                <Fragment key={ev.id}>
                  <tr className="border-b border-[var(--border)]">
                    <td className="px-4 py-3">
                      <Badge tone="accent">{ev.type || ev.event_type}</Badge>
                    </td>
                    <td className="px-4 py-3 capitalize">{String(outcome)}</td>
                    <td className="px-4 py-3 text-xs text-[var(--muted)]">{scoreLine(payload)}</td>
                    <td className="px-4 py-3 text-[var(--muted)]">{formatDate(ev.created_at)}</td>
                    <td className="px-4 py-3">
                      <Badge tone={ev.status === "succeeded" ? "success" : ev.status === "failed" ? "warning" : "neutral"}>
                        {ev.status === "succeeded" ? "Succeeded" : ev.status || "Pending"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        type="button"
                        onClick={() => setExpanded((id) => (id === ev.id ? null : ev.id))}
                        className="text-xs text-[var(--accent)] hover:underline"
                      >
                        {expanded === ev.id ? "Hide" : "View JSON"}
                      </button>
                    </td>
                  </tr>
                  {expanded === ev.id && payload ? (
                    <tr className="border-b border-[var(--border)] bg-black/20">
                      <td colSpan={6} className="px-4 py-3">
                        <pre className="max-h-64 overflow-auto text-xs text-[var(--muted)]">
                          {JSON.stringify(payload, null, 2)}
                        </pre>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
            {!data?.items?.length ? (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-[var(--muted)]">
                  No webhook events yet. Add a webhook under Integration → Webhooks, then run a verification.
                </td>
              </tr>
            ) : null}
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
