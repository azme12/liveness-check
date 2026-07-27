"use client";

import { Bell, CheckCheck, Search, Settings, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { cn, formatDate } from "@/lib/format";

type Notification = {
  id: string;
  type?: string;
  title: string;
  body?: string;
  read: boolean;
  created_at: string;
};

type NotificationsResponse = {
  items: Notification[];
  total: number;
  unread_count: number;
};

export function NotificationsMenu() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [tab, setTab] = useState<"all" | "unread">("all");
  const [days, setDays] = useState<number | null>(null);
  const [data, setData] = useState<NotificationsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    setLoading(true);
    const params = new URLSearchParams({ page: "1", page_size: "30" });
    if (tab === "unread") params.set("unread", "true");
    if (days) params.set("days", String(days));
    if (q.trim().length >= 2) params.set("q", q.trim());
    api<NotificationsResponse>(`/api/auth/notifications?${params}`)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [tab, days, q]);

  useEffect(() => {
    if (!open) return;
    load();
  }, [open, load]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  useEffect(() => {
    api<NotificationsResponse>("/api/auth/notifications?page=1&page_size=1")
      .then(setData)
      .catch(() => undefined);
  }, []);

  async function markRead(id: string) {
    await api(`/api/auth/notifications/${id}/read`, { method: "POST" });
    load();
  }

  async function markAll() {
    await api("/api/auth/notifications/read-all", { method: "POST" });
    load();
  }

  const unread = data?.unread_count ?? 0;

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        title="Notifications"
        onClick={() => setOpen((v) => !v)}
        className="relative hidden sm:grid h-8 w-8 place-items-center rounded-md text-[var(--muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)]"
      >
        <Bell size={16} />
        {unread > 0 ? (
          <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-[var(--accent)]" />
        ) : null}
      </button>

      {open ? (
        <div className="absolute right-0 top-10 z-50 w-[min(92vw,420px)] overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)] shadow-[var(--popover-shadow)]">
          <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-semibold">Notifications</h2>
              <span className="rounded bg-[var(--bg-hover)] px-1.5 py-0.5 text-[10px] font-semibold uppercase text-[var(--muted)]">
                Beta
              </span>
            </div>
            <div className="flex items-center gap-1">
              <Link
                href="/settings/notifications"
                onClick={() => setOpen(false)}
                className="grid h-7 w-7 place-items-center rounded-md text-[var(--muted)] hover:bg-[var(--bg-hover)]"
              >
                <Settings size={14} />
              </Link>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="grid h-7 w-7 place-items-center rounded-md text-[var(--muted)] hover:bg-[var(--bg-hover)]"
              >
                <X size={14} />
              </button>
            </div>
          </div>

          <div className="space-y-3 border-b border-[var(--border)] p-3">
            <div className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2">
              <Search size={14} className="text-[var(--muted)]" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search notifications"
                className="w-full bg-transparent text-sm outline-none placeholder:text-[var(--muted)]"
              />
            </div>
            <div className="flex items-center gap-2">
              {(["all", "unread"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTab(t)}
                  className={cn(
                    "rounded-md px-2.5 py-1 text-xs font-semibold capitalize",
                    tab === t
                      ? "bg-[var(--accent)] text-white"
                      : "bg-[var(--bg-hover)] text-[var(--muted)]",
                  )}
                >
                  {t}
                </button>
              ))}
              <button
                type="button"
                onClick={markAll}
                className="ml-auto inline-flex items-center gap-1 text-xs text-[var(--muted)] hover:text-[var(--text)]"
              >
                <CheckCheck size={12} /> Mark all read
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {[
                { label: "All time", value: null },
                { label: "Today", value: 1 },
                { label: "7 days", value: 7 },
                { label: "30 days", value: 30 },
              ].map((opt) => (
                <button
                  key={opt.label}
                  type="button"
                  onClick={() => setDays(opt.value)}
                  className={cn(
                    "rounded-md px-2 py-1 text-[11px] font-semibold",
                    days === opt.value
                      ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                      : "text-[var(--muted)] hover:bg-[var(--bg-hover)]",
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="max-h-[360px] overflow-y-auto">
            {loading ? (
              <p className="px-4 py-10 text-center text-sm text-[var(--muted)]">Loading…</p>
            ) : !data?.items.length ? (
              <p className="px-4 py-10 text-center text-sm text-[var(--muted)]">No new notifications</p>
            ) : (
              <ul>
                {data.items.map((n) => (
                  <li key={n.id}>
                    <button
                      type="button"
                      onClick={() => !n.read && markRead(n.id)}
                      className={cn(
                        "w-full border-b border-[var(--border)] px-4 py-3 text-left hover:bg-[var(--bg-hover)]",
                        !n.read && "bg-[var(--accent-soft)]/40",
                      )}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium">{n.title}</p>
                        {!n.read ? (
                          <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-[var(--accent)]" />
                        ) : null}
                      </div>
                      {n.body ? (
                        <p className="mt-0.5 line-clamp-2 text-xs text-[var(--muted)]">{n.body}</p>
                      ) : null}
                      <p className="mt-1 text-[11px] text-[var(--muted)]">{formatDate(n.created_at)}</p>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
