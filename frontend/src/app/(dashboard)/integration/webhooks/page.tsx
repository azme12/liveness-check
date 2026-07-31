"use client";

import { ChevronDown, Copy, MoreHorizontal, Plus, X } from "lucide-react";
import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Badge, PageHeader, Panel } from "@/components/AppShell";
import { EnvBanner } from "@/components/EnvBanner";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { WEBHOOK_EVENT_TYPES } from "@/lib/webhookEvents";

type Webhook = {
  id: string;
  url: string;
  secret: string;
  enabled: boolean;
  events: string[];
  description?: string;
  updated_at: string;
};

const DEFAULT_EVENTS = [
  "check.completed",
  "check.completed.clear",
  "check.failed",
  "workflow.session.completed",
];

export default function WebhooksPage() {
  const [items, setItems] = useState<Webhook[]>([]);
  const [reveal, setReveal] = useState(false);
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [selectedEvents, setSelectedEvents] = useState<string[]>(DEFAULT_EVENTS);
  const [eventsOpen, setEventsOpen] = useState(false);
  const [eventQuery, setEventQuery] = useState("");
  const [error, setError] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  async function load() {
    const data = await api<{ items: Webhook[] }>("/api/integration/webhooks");
    setItems(data.items);
  }

  useEffect(() => {
    load().catch(console.error);
  }, []);

  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (!dropdownRef.current?.contains(e.target as Node)) setEventsOpen(false);
    }
    if (eventsOpen) document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [eventsOpen]);

  const filteredEvents = useMemo(() => {
    const q = eventQuery.trim().toLowerCase();
    if (!q) return WEBHOOK_EVENT_TYPES;
    return WEBHOOK_EVENT_TYPES.filter(
      (ev) => ev.value.toLowerCase().includes(q) || ev.description.toLowerCase().includes(q),
    );
  }, [eventQuery]);

  function toggleEvent(value: string) {
    if (value === "*") {
      setSelectedEvents(["*"]);
      return;
    }
    setSelectedEvents((prev) => {
      const withoutAll = prev.filter((e) => e !== "*");
      return withoutAll.includes(value)
        ? withoutAll.filter((e) => e !== value)
        : [...withoutAll, value];
    });
  }

  function resetModal() {
    setOpen(false);
    setUrl("");
    setDescription("");
    setSelectedEvents(DEFAULT_EVENTS);
    setEventsOpen(false);
    setEventQuery("");
    setError("");
  }

  async function onAdd(e: FormEvent) {
    e.preventDefault();
    setError("");
    if (!url.trim().startsWith("https://")) {
      setError("Webhook URL must use HTTPS.");
      return;
    }
    if (selectedEvents.length === 0) {
      setError("Select at least one event.");
      return;
    }
    try {
      await api("/api/integration/webhooks", {
        method: "POST",
        body: JSON.stringify({
          url: url.trim(),
          description: description.trim() || undefined,
          events: selectedEvents,
          enabled: true,
        }),
      });
      resetModal();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add webhook");
    }
  }

  return (
    <div>
      <PageHeader
        title="Webhooks"
        description="Webhooks notify your app when events happen in your Trustanova account (checks, sessions, clients, and more)."
        actions={
          <button
            onClick={() => setOpen(true)}
            className="inline-flex items-center gap-1 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-semibold text-white"
          >
            <Plus size={16} /> Add webhook
          </button>
        }
      />
      <EnvBanner noun="webhooks" />
      <Panel className="mb-4 flex flex-wrap items-center justify-end gap-3 px-4 py-3 text-sm text-[var(--muted)]">
        <button
          onClick={() => setReveal((v) => !v)}
          className="rounded-lg bg-[var(--accent)] px-3 py-1.5 font-semibold text-white"
        >
          {reveal ? "Hide secrets" : "Reveal secrets"}
        </button>
      </Panel>
      <div className="space-y-3">
        {items.length === 0 ? (
          <Panel className="p-8 text-center text-sm text-[var(--muted)]">
            <p>No webhooks yet. Add an HTTPS endpoint to receive verification results (scores, face match, liveness).</p>
            <p className="mt-2">
              Subscribe to <code className="text-[var(--text)]">check.completed</code> and{" "}
              <code className="text-[var(--text)]">workflow.session.completed</code> for full request/response payloads.
            </p>
          </Panel>
        ) : null}
        {items.map((wh) => (
          <Panel key={wh.id} className="p-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 flex-1">
                {wh.description ? (
                  <div className="mb-1 text-sm text-[var(--muted)]">{wh.description}</div>
                ) : null}
                <div className="flex items-center gap-2">
                  <div className="truncate font-mono text-sm">{wh.url}</div>
                  <button
                    onClick={() => navigator.clipboard.writeText(wh.url)}
                    className="text-[var(--muted)] hover:text-white"
                  >
                    <Copy size={14} />
                  </button>
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {wh.events.map((ev) => (
                    <Badge key={ev} tone="accent">
                      {ev}
                    </Badge>
                  ))}
                </div>
                <div className="mt-2 text-xs text-[var(--muted)]">
                  Updated {formatDate(wh.updated_at)} · ID: {wh.id}
                </div>
                <div className="mt-1 font-mono text-xs text-[var(--muted)]">
                  Secret: {reveal ? wh.secret : "••••••••••••••••"}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge tone={wh.enabled ? "success" : "neutral"}>
                  {wh.enabled ? "Enabled" : "Disabled"}
                </Badge>
                <button
                  onClick={async () => {
                    await api(`/api/integration/webhooks/${wh.id}`, {
                      method: "PATCH",
                      body: JSON.stringify({ enabled: !wh.enabled }),
                    });
                    await load();
                  }}
                  className="text-[var(--muted)] hover:text-white"
                >
                  <MoreHorizontal size={16} />
                </button>
              </div>
            </div>
          </Panel>
        ))}
      </div>

      {open ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <form
            onSubmit={onAdd}
            className="w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--bg-panel)] p-5 shadow-2xl"
          >
            <h2 className="mb-4 text-lg font-semibold">Add webhook</h2>

            <label className="mb-4 block text-sm">
              <span className="text-[var(--muted)]">URL*</span>
              <input
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none focus:border-[var(--accent)]"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="e.g. https://www.example.com"
                required
              />
            </label>

            <label className="mb-4 block text-sm">
              <span className="text-[var(--muted)]">Description</span>
              <input
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none focus:border-[var(--accent)]"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What this webhook is used for"
              />
            </label>

            <div className="mb-4 text-sm" ref={dropdownRef}>
              <div className="mb-1 text-[var(--muted)]">EVENTS*</div>
              <button
                type="button"
                onClick={() => setEventsOpen((v) => !v)}
                className="flex w-full items-center justify-between rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-left"
              >
                <span className="truncate text-[var(--muted)]">
                  {selectedEvents.length
                    ? `${selectedEvents.length} event${selectedEvents.length === 1 ? "" : "s"} selected`
                    : "Select event types"}
                </span>
                <ChevronDown size={16} className="shrink-0 text-[var(--muted)]" />
              </button>

              {selectedEvents.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {selectedEvents.map((ev) => (
                    <span
                      key={ev}
                      className="inline-flex items-center gap-1 rounded bg-[var(--accent-soft)] px-2 py-0.5 text-xs text-[var(--accent)]"
                    >
                      {ev}
                      <button
                        type="button"
                        onClick={() => toggleEvent(ev)}
                        className="hover:text-white"
                        aria-label={`Remove ${ev}`}
                      >
                        <X size={12} />
                      </button>
                    </span>
                  ))}
                </div>
              ) : null}

              {eventsOpen ? (
                <div className="relative z-10 mt-2 overflow-hidden rounded-lg border border-[var(--border)] bg-[#12151c] shadow-xl">
                  <div className="border-b border-[var(--border)] p-2">
                    <input
                      autoFocus
                      value={eventQuery}
                      onChange={(e) => setEventQuery(e.target.value)}
                      placeholder="Search events"
                      className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-sm outline-none focus:border-[var(--accent)]"
                    />
                  </div>
                  <ul className="max-h-56 overflow-y-auto py-1">
                    {filteredEvents.map((ev) => {
                      const checked = selectedEvents.includes(ev.value);
                      return (
                        <li key={ev.value}>
                          <button
                            type="button"
                            onClick={() => toggleEvent(ev.value)}
                            className={`flex w-full items-start gap-2 px-3 py-2 text-left text-sm hover:bg-[var(--accent-soft)] ${
                              checked ? "bg-[var(--accent-soft)] text-[var(--accent)]" : ""
                            }`}
                          >
                            <span
                              className={`mt-0.5 grid h-4 w-4 shrink-0 place-items-center rounded border ${
                                checked
                                  ? "border-[var(--accent)] bg-[var(--accent)] text-black"
                                  : "border-[var(--border)]"
                              }`}
                            >
                              {checked ? "✓" : ""}
                            </span>
                            <span>
                              <span className="font-mono text-xs">{ev.value}</span>
                              <span className="mt-0.5 block text-xs text-[var(--muted)]">
                                {ev.description}
                              </span>
                            </span>
                          </button>
                        </li>
                      );
                    })}
                    {filteredEvents.length === 0 ? (
                      <li className="px-3 py-4 text-center text-xs text-[var(--muted)]">No events match</li>
                    ) : null}
                  </ul>
                </div>
              ) : null}
            </div>

            {error ? <p className="mb-3 text-sm text-[var(--danger)]">{error}</p> : null}

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={resetModal}
                className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="rounded-lg bg-[var(--success)] px-4 py-2 text-sm font-semibold text-black"
              >
                Add webhook
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}
