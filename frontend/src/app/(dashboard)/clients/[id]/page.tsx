"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Copy, MoreHorizontal } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Panel } from "@/components/AppShell";
import { Footer } from "@/components/Footer";
import { api, Paginated } from "@/lib/api";
import { verifyUrl } from "@/lib/verifyApi";
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
  result?: {
    document?: { quality_score?: number; document_type?: string | null };
    biometric?: {
      liveness?: string;
      liveness_score?: number;
      face_match_score?: number | null;
      face_match_passed?: boolean | null;
    };
    signals?: { scores?: Record<string, unknown> };
  } | null;
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
  const [workflowsLoading, setWorkflowsLoading] = useState(false);
  const [workflowsError, setWorkflowsError] = useState("");
  const [startOpen, setStartOpen] = useState(false);
  const [workflowId, setWorkflowId] = useState("");
  const [method, setMethod] = useState<"upload" | "email" | "link" | "phone">("upload");
  const [deliveryEmail, setDeliveryEmail] = useState("");
  const [starting, setStarting] = useState(false);
  const [startResult, setStartResult] = useState<StartResponse | null>(null);
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [documentType, setDocumentType] = useState("fayda");
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [livePhotoFile, setLivePhotoFile] = useState<File | null>(null);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [liveChecks, setLiveChecks] = useState<Check[]>([]);

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
    setConsentAccepted(false);
    setDocumentFile(null);
    setLivePhotoFile(null);
    setUploadMessage("");
    setUploadError("");
    setLiveChecks([]);
    setWorkflowsLoading(true);
    setWorkflowsError("");
    try {
      const res = await api<Paginated<{ id: string; name: string }>>("/api/workflows?page=1&page_size=50");
      setWorkflows(res.items);
      const first = res.items[0];
      setWorkflowId(first?.id || "");
      setDeliveryEmail(client?.email || "");
    } catch (err) {
      setWorkflowsError(err instanceof Error ? err.message : "Failed to load workflows");
      setWorkflows([]);
      setWorkflowId("");
    } finally {
      setWorkflowsLoading(false);
    }
  }

  async function startVerification() {
    setStarting(true);
    try {
      const res = await api<StartResponse>("/api/sessions", {
        method: "POST",
        body: JSON.stringify({
          client_id: params.id,
          workflow_id: workflowId || null,
          method,
          delivery_email: deliveryEmail || client?.email || null,
        }),
      });
      setStartResult(res);
      if (method === "upload" && res.share_token) {
        await fetch(verifyUrl(`/api/verify/${res.share_token}/progress`), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ stage: "consent" }),
        }).catch(console.error);
      }
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

  const verifyToken = startResult?.share_token || "";

  async function refreshVerifyChecks() {
    if (!verifyToken) return;
    const res = await fetch(verifyUrl(`/api/verify/${verifyToken}`), { cache: "no-store" });
    if (!res.ok) return;
    const data = (await res.json()) as { checks?: Check[] };
    setLiveChecks(data.checks || []);
    api<Paginated<Check>>(`/api/clients/${params.id}/checks?page=1&page_size=10`)
      .then(setChecks)
      .catch(console.error);
    loadClient();
  }

  async function uploadVerificationPhoto(kind: "document" | "live-photo") {
    if (!verifyToken) return;
    const file = kind === "document" ? documentFile : livePhotoFile;
    if (!file) return;
    if (kind === "document" && !consentAccepted) {
      setUploadError("Accept consent before uploading.");
      return;
    }
    setUploadBusy(true);
    setUploadError("");
    setUploadMessage("");
    try {
      const form = new FormData();
      form.append("file", file);
      if (kind === "document") {
        form.append("document_type", documentType);
        form.append("issuing_country", client?.nationality || "Ethiopia");
      }
      const res = await fetch(verifyUrl(`/api/verify/${verifyToken}/${kind}`), {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || `Upload failed (${kind})`);
      }
      await refreshVerifyChecks();
      setUploadMessage(
        kind === "document"
          ? "Document uploaded. Now upload a selfie to run liveness + face match."
          : "Selfie uploaded. Scores ready — webhook POST sent to your configured URL. Check Integration → Events.",
      );
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploadBusy(false);
    }
  }

  const identityCheck = useMemo(() => {
    return liveChecks.find((c) => c.type === "identity_check" && c.status === "complete") || null;
  }, [liveChecks]);

  const scores = (identityCheck?.result?.signals?.scores || null) as Record<string, unknown> | null;

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
                    ["upload", "Upload photos here", "Upload document + selfie on this screen."],
                    ["link", "Manual link", "Copy the verification link and send it to the client."],
                    ["email", "Email invite", "Open a ready-to-send email with the secure verification link."],
                    ["phone", "Continue on phone", "Show a QR/mobile link for the client."],
                  ].map(([id, label, desc]) => (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setMethod(id as "upload" | "email" | "link" | "phone")}
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
                    disabled={workflowsLoading}
                    className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-panel)] px-3 py-2 text-[var(--text)] outline-none disabled:opacity-60"
                  >
                    {workflowsLoading ? (
                      <option value="">Loading workflows…</option>
                    ) : workflows.length === 0 ? (
                      <option value="">Default verification (identity check)</option>
                    ) : (
                      workflows.map((w) => (
                        <option key={w.id} value={w.id} className="bg-[var(--bg-panel)] text-[var(--text)]">
                          {w.name}
                        </option>
                      ))
                    )}
                  </select>
                </label>
                {workflowsError ? (
                  <p className="mt-2 text-xs text-red-400">{workflowsError}</p>
                ) : null}
                {!workflowsLoading && workflows.length === 0 && !workflowsError ? (
                  <p className="mt-2 text-xs text-[var(--muted)]">
                    No custom workflow yet — a default identity check will run. Create one under{" "}
                    <Link href="/workflows" className="text-[var(--accent)] hover:underline">
                      Workflows
                    </Link>
                    .
                  </p>
                ) : null}
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
                  disabled={starting || workflowsLoading}
                  onClick={startVerification}
                  className="mt-4 w-full rounded-lg bg-[var(--accent)] px-4 py-2 font-semibold text-white disabled:opacity-60"
                >
                  {starting ? "Creating…" : method === "upload" ? "Create & upload photos" : "Create verification"}
                </button>
              </div>

              <div>
                <div className="mb-2 text-sm font-medium">
                  {method === "upload" && startResult ? "Step 3: Upload document + selfie" : "Step 3: Share / continue"}
                </div>
                {startResult && method === "upload" ? (
                  <div className="space-y-3 rounded-lg border border-[var(--border)] bg-[var(--bg)] p-3 text-sm">
                    <label className="flex items-start gap-2">
                      <input
                        type="checkbox"
                        checked={consentAccepted}
                        onChange={(e) => setConsentAccepted(e.target.checked)}
                        className="mt-1"
                      />
                      <span className="text-[var(--muted)]">
                        Client consents to identity verification and biometric processing.
                      </span>
                    </label>
                    <label className="block">
                      <span className="text-xs text-[var(--muted)]">Document type</span>
                      <select
                        value={documentType}
                        onChange={(e) => setDocumentType(e.target.value)}
                        className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg-panel)] px-3 py-2"
                      >
                        <option value="fayda">Fayda ID</option>
                        <option value="kebele_id">Kebele ID</option>
                        <option value="national_id">National ID</option>
                        <option value="passport">Passport</option>
                        <option value="driving_license">Driving license</option>
                      </select>
                    </label>
                    <label className="block rounded-lg border border-dashed border-[var(--border)] p-3">
                      <span className="text-xs text-[var(--muted)]">1. Document photo (ID / passport)</span>
                      <input
                        className="mt-2 block w-full text-xs"
                        type="file"
                        accept="image/*"
                        onChange={(e) => setDocumentFile(e.target.files?.[0] || null)}
                      />
                      <button
                        type="button"
                        disabled={uploadBusy || !documentFile || !consentAccepted}
                        onClick={() => uploadVerificationPhoto("document")}
                        className="mt-2 w-full rounded-lg border border-[var(--border)] px-3 py-2 disabled:opacity-50"
                      >
                        {uploadBusy ? "Uploading…" : "Upload document"}
                      </button>
                    </label>
                    <label className="block rounded-lg border border-dashed border-[var(--border)] p-3">
                      <span className="text-xs text-[var(--muted)]">2. Selfie / live photo</span>
                      <input
                        className="mt-2 block w-full text-xs"
                        type="file"
                        accept="image/*"
                        onChange={(e) => setLivePhotoFile(e.target.files?.[0] || null)}
                      />
                      <button
                        type="button"
                        disabled={uploadBusy || !livePhotoFile}
                        onClick={() => uploadVerificationPhoto("live-photo")}
                        className="mt-2 w-full rounded-lg bg-[var(--accent)] px-3 py-2 font-semibold text-white disabled:opacity-50"
                      >
                        {uploadBusy ? "Running check…" : "Upload selfie & run check"}
                      </button>
                    </label>
                    {uploadError ? <div className="text-xs text-red-400">{uploadError}</div> : null}
                    {uploadMessage ? <div className="text-xs text-[var(--accent)]">{uploadMessage}</div> : null}
                    {identityCheck ? (
                      <div className="rounded-lg border border-[var(--border)] bg-black/20 p-3 text-xs">
                        <div className="mb-2 font-medium text-white">Verification scores</div>
                        <div className="grid gap-1 text-[var(--muted)]">
                          <div>Outcome: <span className="capitalize text-white">{identityCheck.outcome || "—"}</span></div>
                          <div>Document: {String(scores?.document_type || documentType)}</div>
                          <div>Doc quality: {typeof scores?.document_quality === "number" ? Number(scores.document_quality).toFixed(2) : "—"}</div>
                          <div>Liveness: {typeof scores?.liveness_score === "number" ? Number(scores.liveness_score).toFixed(2) : "—"}</div>
                          <div>Face match: {typeof scores?.face_match_score === "number" ? Number(scores.face_match_score).toFixed(2) : "—"}</div>
                        </div>
                        <p className="mt-2 text-[10px] text-[var(--muted)]">
                          Webhook events <code className="text-white">check.completed</code> and{" "}
                          <code className="text-white">check.completed.clear</code> were sent to your configured endpoints.
                        </p>
                      </div>
                    ) : null}
                    {shareLink ? (
                      <button
                        type="button"
                        onClick={() => window.open(shareLink, "_blank", "noopener,noreferrer")}
                        className="w-full rounded-lg border border-[var(--border)] px-3 py-2 text-xs"
                      >
                        Open hosted verify page
                      </button>
                    ) : null}
                  </div>
                ) : startResult ? (
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
                    {method === "upload"
                      ? "Create the verification first, then upload the document photo and selfie here."
                      : "Create the verification first. Then you can copy the link, open the hosted flow, or use phone QR."}
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
            <th className="py-2 text-left font-medium">Face match</th>
            <th className="py-2 text-left font-medium">Liveness</th>
            <th className="py-2 text-left font-medium">Completed</th>
          </tr>
        </thead>
        <tbody>
          {(data?.items || []).map((c) => {
            const s = c.result?.signals?.scores as Record<string, unknown> | undefined;
            const face = s?.face_match_score ?? c.result?.biometric?.face_match_score;
            const live = s?.liveness_score ?? c.result?.biometric?.liveness_score;
            return (
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
              <td className="py-3 text-[var(--muted)]">
                {typeof face === "number" ? face.toFixed(2) : "—"}
              </td>
              <td className="py-3 text-[var(--muted)]">
                {typeof live === "number" ? live.toFixed(2) : "—"}
              </td>
              <td className="py-3 text-[var(--muted)]">{formatDate(c.completed_at || c.created_at)}</td>
            </tr>
          );})}
          {!data?.items?.length ? (
            <tr>
              <td colSpan={6} className="py-8 text-center text-[var(--muted)]">
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
