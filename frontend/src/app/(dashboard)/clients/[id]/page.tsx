"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Copy, MoreHorizontal } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
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
  workflow_name?: string;
  method?: string;
  current_stage?: string;
  share_token?: string;
  created_at: string;
};

type StartResponse = {
  id: string;
  client?: { id: string; name: string; email?: string | null };
  workflow_id?: string;
  workflow_name?: string;
  method?: string;
  delivery_email?: string | null;
  share_url?: string;
  share_token?: string;
  current_stage?: string;
  checks?: Array<{ id: string; type: string; label?: string; status: string }>;
  sdk?: {
    token: string;
    publishable_key?: string;
    script_url?: string;
    hosted_url?: string;
    snippet?: string;
  };
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
  const [method, setMethod] = useState<"email" | "link" | "phone" | "sdk">("email");
  const [deliveryEmail, setDeliveryEmail] = useState("");
  const [starting, setStarting] = useState(false);
  const [startResult, setStartResult] = useState<StartResponse | null>(null);

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
    setStartResult(null);
    try {
      const res = await api<Paginated<{ id: string; name: string }>>("/api/workflows?page=1&page_size=50");
      setWorkflows(res.items);
      const first = res.items[0];
      if (first) setWorkflowId(first.id);
      setDeliveryEmail(client?.email || "");
    } catch (err) {
      console.error(err);
    }
  }

  async function startVerification() {
    if (!workflowId) return;
    setStarting(true);
    try {
      const res = await api<StartResponse>("/api/sessions", {
        method: "POST",
        body: JSON.stringify({
          client_id: params.id,
          workflow_id: workflowId,
          method,
          delivery_email: deliveryEmail || client?.email || null,
          hosted_origin: typeof window !== "undefined" ? window.location.origin : null,
        }),
      });
      setStartResult(res);
      setTab("sessions");
      api<Paginated<Session>>(`/api/clients/${params.id}/sessions?page=1&page_size=10`)
        .then(setSessions)
        .catch(console.error);
      api<Paginated<Check>>(`/api/clients/${params.id}/checks?page=1&page_size=10`)
        .then(setChecks)
        .catch(console.error);
      loadClient();
      if (method === "email" && (deliveryEmail || client?.email)) {
        const inviteLink =
          typeof window !== "undefined" && res.share_url ? `${window.location.origin}${res.share_url}` : "";
        window.location.href = `mailto:${encodeURIComponent(deliveryEmail || client?.email || "")}?subject=${encodeURIComponent(
          "Verify your identity",
        )}&body=${encodeURIComponent(`Open this secure verification link:\n\n${inviteLink}`)}`;
      }
    } catch (err) {
      console.error(err);
    } finally {
      setStarting(false);
    }
  }

  const shareLink = useMemo(() => {
    if (!startResult?.share_url || typeof window === "undefined") return "";
    return `${window.location.origin}${startResult.share_url}`;
  }, [startResult]);

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
          <div className="w-full max-w-4xl rounded-xl border border-[var(--border)] bg-[var(--bg-panel)] p-5">
            <h2 className="text-lg font-semibold">Start verification</h2>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Keep the same client ID, choose a workflow, and create a secure verification link.
            </p>

            <div className="mt-4 grid gap-5 lg:grid-cols-3">
              <div>
                <div className="mb-2 text-sm font-medium">Step 1: Choose method</div>
                <div className="space-y-2">
                  {[
                    ["email", "Email invite", "Open a ready-to-send email with the secure verification link."],
                    ["link", "Manual link", "Copy the verification link and send it manually."],
                    ["phone", "Continue on phone", "Show a QR/mobile link for the client."],
                    ["sdk", "Use SDK token", "Create a token for your web/mobile SDK integration."],
                  ].map(([id, label, desc]) => (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setMethod(id as "email" | "link" | "phone" | "sdk")}
                      className={cn(
                        "block w-full rounded-lg border px-3 py-3 text-left",
                        method === id
                          ? "border-[var(--accent)] bg-[var(--accent-soft)]"
                          : "border-[var(--border)] hover:bg-[var(--bg-hover)]",
                      )}
                    >
                      <div className="font-medium">{label}</div>
                      <div className="mt-1 text-xs text-[var(--muted)]">{desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <div className="mb-2 text-sm font-medium">Step 2: Choose verification flow</div>
                <label className="block text-sm">
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
                {method === "email" ? (
                  <label className="mt-4 block text-sm">
                    <span className="text-[var(--muted)]">Recipient email</span>
                    <input
                      value={deliveryEmail}
                      onChange={(e) => setDeliveryEmail(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none"
                      placeholder="client@email.com"
                      type="email"
                    />
                  </label>
                ) : null}
                <button
                  type="button"
                  disabled={starting || !workflowId}
                  onClick={startVerification}
                  className="mt-4 w-full rounded-lg bg-[var(--accent)] px-4 py-2 font-semibold text-white disabled:opacity-60"
                >
                  {starting ? "Creating…" : "Create verification"}
                </button>
              </div>

              <div>
                <div className="mb-2 text-sm font-medium">Step 3: Share / continue</div>
                {startResult ? (
                  <div className="space-y-3 rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3 text-sm">
                    <div className="text-[var(--muted)]">
                      Session created for <span className="text-white">{startResult.client?.name || client.name}</span>.
                    </div>
                    <div>
                      <div className="mb-1 text-xs text-[var(--muted)]">Client ID</div>
                      <code className="break-all text-xs">{client.id}</code>
                    </div>
                    <div>
                      <div className="mb-1 text-xs text-[var(--muted)]">Verification link</div>
                      <code className="block break-all rounded bg-black/20 px-2 py-2 text-xs">{shareLink || "—"}</code>
                    </div>
                    {method === "phone" ? (
                      <div>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={`https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(shareLink)}`}
                          alt="Verification QR"
                          className="rounded bg-white p-2"
                          width={160}
                          height={160}
                        />
                      </div>
                    ) : null}
                    {method === "sdk" ? (
                      <div className="space-y-2">
                        <div>
                          <div className="mb-1 text-xs text-[var(--muted)]">SDK token</div>
                          <code className="break-all text-xs">{startResult.sdk?.token || startResult.share_token}</code>
                        </div>
                        {startResult.sdk?.publishable_key ? (
                          <div>
                            <div className="mb-1 text-xs text-[var(--muted)]">Publishable key</div>
                            <code className="break-all text-xs">{startResult.sdk.publishable_key}</code>
                          </div>
                        ) : null}
                        {startResult.sdk?.snippet ? (
                          <div>
                            <div className="mb-1 flex items-center justify-between gap-2 text-xs text-[var(--muted)]">
                              <span>Embed snippet</span>
                              <button
                                type="button"
                                onClick={() => navigator.clipboard.writeText(startResult.sdk?.snippet || "")}
                                className="text-[var(--accent)] hover:underline"
                              >
                                Copy
                              </button>
                            </div>
                            <pre className="max-h-48 overflow-auto rounded bg-black/20 p-2 text-[11px] leading-relaxed text-[var(--muted)]">
                              {startResult.sdk.snippet}
                            </pre>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                    <div className="flex flex-wrap gap-2">
                      {shareLink ? (
                        <button
                          type="button"
                          onClick={() => navigator.clipboard.writeText(shareLink)}
                          className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm"
                        >
                          Copy link
                        </button>
                      ) : null}
                      {shareLink ? (
                        <button
                          type="button"
                          onClick={() => window.open(shareLink, "_blank", "noopener,noreferrer")}
                          className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm"
                        >
                          Open flow
                        </button>
                      ) : null}
                    </div>
                    <div className="text-xs text-[var(--muted)]">
                      Checks are created immediately from the selected workflow and will complete as the client moves through
                      the hosted stages.
                    </div>
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed border-[var(--border)] p-4 text-sm text-[var(--muted)]">
                    Create the verification first. Then you can copy the link, open the hosted flow, use phone QR, or pass the
                    SDK token into your app.
                  </div>
                )}
              </div>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setStartOpen(false)}
                className="rounded-lg border border-[var(--border)] px-4 py-2"
              >
                Close
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
            <th className="py-2 text-left font-medium">Method</th>
            <th className="py-2 text-left font-medium">Stage</th>
            <th className="py-2 text-left font-medium">Status</th>
            <th className="py-2 text-left font-medium">Created</th>
          </tr>
        </thead>
        <tbody>
          {(data?.items || []).map((s) => (
            <tr key={s.id} className="border-b border-[var(--border)] last:border-0">
              <td className="py-3 font-mono text-xs">{s.id}</td>
              <td className="py-3 text-[var(--muted)]">{s.workflow_name || s.workflow_id || "—"}</td>
              <td className="py-3 capitalize text-[var(--muted)]">{s.method || "link"}</td>
              <td className="py-3 capitalize text-[var(--muted)]">{(s.current_stage || "consent").replaceAll("_", " ")}</td>
              <td className="py-3 capitalize">{s.status}</td>
              <td className="py-3 text-[var(--muted)]">{formatDate(s.created_at)}</td>
            </tr>
          ))}
          {!data?.items?.length ? (
            <tr>
              <td colSpan={6} className="py-8 text-center text-[var(--muted)]">
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
      {label.replaceAll("_", " ")} — not configured yet.
    </div>
  );
}
