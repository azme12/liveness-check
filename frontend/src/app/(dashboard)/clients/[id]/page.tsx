"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Copy, MoreHorizontal } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Badge, Panel } from "@/components/AppShell";
import { Footer } from "@/components/Footer";
import { api, Paginated } from "@/lib/api";
import { cn, formatDate } from "@/lib/format";

type Client = {
  id: string;
  name: string;
  email?: string | null;
  first_name?: string | null;
  middle_name?: string | null;
  last_name?: string | null;
  mobile?: string | null;
  nationality?: string | null;
  date_of_birth?: string | null;
  external_id?: string | null;
  type: string;
  risk: string;
  created_at: string;
  updated_at?: string;
  counts?: { checks: number; sessions: number; documents: number };
};

type Check = {
  id: string;
  type: string;
  status: string;
  outcome?: string;
  monitoring?: string;
  created_at: string;
  completed_at?: string;
};

type Session = {
  id: string;
  status: string;
  workflow_id?: string;
  created_at: string;
};

type DocumentRow = {
  id: string;
  document_type?: string;
  status?: string;
  created_at: string;
};

type Tab =
  | "general"
  | "checks"
  | "sessions"
  | "documents"
  | "addresses"
  | "notes"
  | "metadata"
  | "aml"
  | "cases"
  | "audit"
  | "api";

export default function ClientDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("general");
  const [client, setClient] = useState<Client | null>(null);
  const [checks, setChecks] = useState<Paginated<Check> | null>(null);
  const [sessions, setSessions] = useState<Paginated<Session> | null>(null);
  const [documents, setDocuments] = useState<Paginated<DocumentRow> | null>(null);
  const [workflows, setWorkflows] = useState<{ id: string; name: string }[]>([]);
  const [startOpen, setStartOpen] = useState(false);
  const [workflowId, setWorkflowId] = useState("");
  const [starting, setStarting] = useState(false);

  const loadClient = useCallback(() => {
    api<Client>(`/api/clients/${params.id}`)
      .then(setClient)
      .catch(() => router.replace("/clients"));
  }, [params.id, router]);

  useEffect(() => {
    loadClient();
  }, [loadClient]);

  useEffect(() => {
    if (tab === "checks") {
      api<Paginated<Check>>(`/api/clients/${params.id}/checks?page=1&page_size=10`)
        .then(setChecks)
        .catch(console.error);
    }
    if (tab === "sessions") {
      api<Paginated<Session>>(`/api/clients/${params.id}/sessions?page=1&page_size=10`)
        .then(setSessions)
        .catch(console.error);
    }
    if (tab === "documents") {
      api<Paginated<DocumentRow>>(`/api/clients/${params.id}/documents?page=1&page_size=10`)
        .then(setDocuments)
        .catch(console.error);
    }
  }, [tab, params.id]);

  async function openStart() {
    setStartOpen(true);
    try {
      const res = await api<Paginated<{ id: string; name: string }>>("/api/workflows?page=1&page_size=50");
      setWorkflows(res.items);
      const first = res.items[0];
      if (first) setWorkflowId(first.id);
    } catch (err) {
      console.error(err);
    }
  }

  async function startVerification() {
    if (!workflowId) return;
    setStarting(true);
    try {
      await api("/api/sessions", {
        method: "POST",
        body: JSON.stringify({ client_id: params.id, workflow_id: workflowId }),
      });
      setStartOpen(false);
      setTab("sessions");
      api<Paginated<Session>>(`/api/clients/${params.id}/sessions?page=1&page_size=10`)
        .then(setSessions)
        .catch(console.error);
      loadClient();
    } catch (err) {
      console.error(err);
    } finally {
      setStarting(false);
    }
  }

  if (!client) {
    return <div className="text-[var(--muted)]">Loading client…</div>;
  }

  const nav: { group: string; items: { id: Tab; label: string; count?: number }[] }[] = [
    {
      group: "KEY INFORMATION",
      items: [
        { id: "general", label: "General" },
        { id: "addresses", label: "Addresses" },
        { id: "documents", label: "Documents", count: client.counts?.documents },
        { id: "notes", label: "Notes" },
        { id: "metadata", label: "Metadata" },
      ],
    },
    {
      group: "DUE DILIGENCE",
      items: [
        { id: "sessions", label: "Sessions", count: client.counts?.sessions },
        { id: "checks", label: "Checks", count: client.counts?.checks },
        { id: "aml", label: "AML Risk" },
        { id: "cases", label: "Cases" },
      ],
    },
    {
      group: "ACTIVITY LOGS",
      items: [
        { id: "audit", label: "Audit Log" },
        { id: "api", label: "API Log" },
      ],
    },
  ];

  return (
    <div>
      <div className="mb-2 text-sm text-[var(--muted)]">
        <Link href="/clients" className="hover:text-white">
          Clients
        </Link>
        <span className="mx-2">›</span>
        <span className="text-white">{client.name}</span>
      </div>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="grid h-14 w-14 place-items-center rounded-lg bg-[var(--accent-soft)] text-lg font-semibold text-[var(--accent)]">
            {client.name.slice(0, 1).toUpperCase()}
          </div>
          <div>
            <h1 className="text-2xl font-semibold">{client.name}</h1>
            <div className="text-sm text-[var(--muted)]">{client.email || "—"}</div>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={openStart}
            className="rounded-lg border border-[var(--success)] px-4 py-2 text-sm font-semibold text-[var(--success)] hover:bg-[rgba(34,197,94,0.08)]"
          >
            Start verification
          </button>
          <button className="grid h-10 w-10 place-items-center rounded-lg border border-[var(--border)] text-[var(--muted)]">
            <MoreHorizontal size={16} />
          </button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[220px_1fr]">
        <aside className="space-y-4">
          {nav.map((group) => (
            <div key={group.group}>
              <div className="mb-2 text-[10px] font-semibold tracking-wider text-[var(--muted)]">{group.group}</div>
              <div className="space-y-1">
                {group.items.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setTab(item.id)}
                    className={cn(
                      "flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm",
                      tab === item.id
                        ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                        : "text-[var(--muted)] hover:bg-[var(--bg-hover)] hover:text-white",
                    )}
                  >
                    <span>{item.label}</span>
                    {typeof item.count === "number" && item.count > 0 ? (
                      <span className="rounded-full bg-[var(--bg-hover)] px-1.5 text-[11px]">{item.count}</span>
                    ) : null}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </aside>

        <Panel className="p-5">
          {tab === "general" ? <GeneralTab client={client} /> : null}
          {tab === "checks" ? <ChecksTab data={checks} /> : null}
          {tab === "sessions" ? <SessionsTab data={sessions} /> : null}
          {tab === "documents" ? <DocumentsTab data={documents} /> : null}
          {tab !== "general" && tab !== "checks" && tab !== "sessions" && tab !== "documents" ? (
            <EmptyState label={tab} />
          ) : null}
        </Panel>
      </div>

      {startOpen ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--bg-panel)] p-5">
            <h2 className="text-lg font-semibold">Start verification</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">Choose a workflow to run for this client.</p>
            <label className="mt-4 block text-sm">
              <span className="text-[var(--muted)]">Workflow</span>
              <select
                value={workflowId}
                onChange={(e) => setWorkflowId(e.target.value)}
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none"
              >
                {workflows.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </select>
            </label>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setStartOpen(false)}
                className="rounded-lg border border-[var(--border)] px-4 py-2"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={starting || !workflowId}
                onClick={startVerification}
                className="rounded-lg bg-[var(--accent)] px-4 py-2 font-semibold text-white disabled:opacity-60"
              >
                {starting ? "Starting…" : "Start"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function GeneralTab({ client }: { client: Client }) {
  const fields = [
    { label: "First Name", value: client.first_name },
    { label: "Middle Name", value: client.middle_name },
    { label: "Last Name", value: client.last_name },
    { label: "Email Address", value: client.email },
    { label: "Date of Birth", value: client.date_of_birth },
    { label: "Nationality", value: client.nationality },
    { label: "Mobile", value: client.mobile },
    { label: "Type", value: client.type },
    { label: "Risk", value: client.risk },
    { label: "Created On", value: formatDate(client.created_at) },
    { label: "External ID", value: client.external_id, mono: true },
    { label: "Client ID", value: client.id, mono: true },
  ];

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">General</h2>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {fields.map((f) => (
          <div key={f.label}>
            <div className="text-xs text-[var(--muted)]">{f.label}</div>
            <div className={cn("mt-1 text-sm", f.mono && "break-all font-mono text-xs")}>
              {f.value || "—"}
              {f.mono && f.value ? (
                <button
                  type="button"
                  className="ml-1 inline text-[var(--muted)] hover:text-white"
                  onClick={() => navigator.clipboard.writeText(String(f.value))}
                >
                  <Copy size={11} className="inline" />
                </button>
              ) : null}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-6 text-xs text-[var(--muted)]">
        Updated on {formatDate(client.updated_at || client.created_at)}
      </p>
    </div>
  );
}

function ChecksTab({ data }: { data: Paginated<Check> | null }) {
  return (
    <div>
      <h2 className="mb-4 text-lg font-semibold">Checks</h2>
      <table className="w-full text-sm">
        <thead className="text-[var(--muted)]">
          <tr className="border-b border-[var(--border)]">
            <th className="py-2 text-left font-medium">Type</th>
            <th className="py-2 text-left font-medium">Status</th>
            <th className="py-2 text-left font-medium">Outcome</th>
            <th className="py-2 text-left font-medium">Monitoring</th>
            <th className="py-2 text-left font-medium">Completed</th>
          </tr>
        </thead>
        <tbody>
          {(data?.items || []).map((c) => (
            <tr key={c.id} className="border-b border-[var(--border)] last:border-0">
              <td className="py-3">{c.type.replaceAll("_", " ")}</td>
              <td className="py-3 capitalize">{c.status}</td>
              <td className="py-3">
                {c.outcome === "clear" ? (
                  <Badge tone="success">Clear</Badge>
                ) : (
                  <span className="capitalize text-[var(--muted)]">{c.outcome || "—"}</span>
                )}
              </td>
              <td className="py-3 text-[var(--muted)]">{c.monitoring || "N/A"}</td>
              <td className="py-3 text-[var(--muted)]">{formatDate(c.completed_at || c.created_at)}</td>
            </tr>
          ))}
          {!data?.items?.length ? (
            <tr>
              <td colSpan={5} className="py-8 text-center text-[var(--muted)]">
                No checks yet. Start a verification to create checks.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
      {data ? (
        <Footer
          total={data.total}
          page={data.page}
          pages={data.pages}
          pageSize={data.page_size}
          onPage={() => undefined}
          onPageSize={() => undefined}
        />
      ) : null}
    </div>
  );
}

function SessionsTab({ data }: { data: Paginated<Session> | null }) {
  return (
    <div>
      <h2 className="mb-4 text-lg font-semibold">Sessions</h2>
      <table className="w-full text-sm">
        <thead className="text-[var(--muted)]">
          <tr className="border-b border-[var(--border)]">
            <th className="py-2 text-left font-medium">Session ID</th>
            <th className="py-2 text-left font-medium">Workflow</th>
            <th className="py-2 text-left font-medium">Status</th>
            <th className="py-2 text-left font-medium">Created</th>
          </tr>
        </thead>
        <tbody>
          {(data?.items || []).map((s) => (
            <tr key={s.id} className="border-b border-[var(--border)] last:border-0">
              <td className="py-3 font-mono text-xs">{s.id}</td>
              <td className="py-3 text-[var(--muted)]">{s.workflow_id || "—"}</td>
              <td className="py-3 capitalize">{s.status}</td>
              <td className="py-3 text-[var(--muted)]">{formatDate(s.created_at)}</td>
            </tr>
          ))}
          {!data?.items?.length ? (
            <tr>
              <td colSpan={4} className="py-8 text-center text-[var(--muted)]">
                No sessions yet.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

function DocumentsTab({ data }: { data: Paginated<DocumentRow> | null }) {
  return (
    <div>
      <h2 className="mb-4 text-lg font-semibold">Documents</h2>
      <table className="w-full text-sm">
        <thead className="text-[var(--muted)]">
          <tr className="border-b border-[var(--border)]">
            <th className="py-2 text-left font-medium">ID</th>
            <th className="py-2 text-left font-medium">Type</th>
            <th className="py-2 text-left font-medium">Status</th>
            <th className="py-2 text-left font-medium">Added</th>
          </tr>
        </thead>
        <tbody>
          {(data?.items || []).map((d) => (
            <tr key={d.id} className="border-b border-[var(--border)] last:border-0">
              <td className="py-3 font-mono text-xs">{d.id}</td>
              <td className="py-3">{d.document_type || "—"}</td>
              <td className="py-3 capitalize">{d.status || "—"}</td>
              <td className="py-3 text-[var(--muted)]">{formatDate(d.created_at)}</td>
            </tr>
          ))}
          {!data?.items?.length ? (
            <tr>
              <td colSpan={4} className="py-8 text-center text-[var(--muted)]">
                No documents uploaded.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <div className="py-12 text-center text-sm text-[var(--muted)]">
      {label.replaceAll("_", " ")} — coming soon for this demo.
    </div>
  );
}
