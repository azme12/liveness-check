"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { HelpCircle, Play, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge } from "@/components/AppShell";
import { api } from "@/lib/api";
import { cn, formatDate } from "@/lib/format";

type Step = { type: string; label: string };
type Workflow = {
  id: string;
  name: string;
  description: string;
  status: string;
  version: number;
  steps: Step[];
  updated_at: string;
};

const CATALOG = [
  { group: "GOVERNMENT ID VERIFICATION", items: [{ type: "document_check", label: "Document Check", desc: "Verify government-issued ID." }] },
  {
    group: "BIOMETRIC & LIVENESS CHECK",
    items: [
      { type: "identity_check", label: "Identity Check", desc: "Biometric & liveness verification (selfie).", enabled: true },
      { type: "enhanced_identity_check", label: "Enhanced Identity Check", desc: "Biometric & liveness verification (video)." },
      { type: "age_estimation_check", label: "Age Estimation Check", desc: "Estimate client age from selfie." },
    ],
  },
  {
    group: "ADDRESS & IDENTITY DATA CHECK",
    items: [
      { type: "multi_bureau_check", label: "Multi Bureau Check", desc: "Verify client details via trusted sources." },
      { type: "proof_of_address_check", label: "Proof of Address Check", desc: "Verify POA documents." },
    ],
  },
  {
    group: "SANCTIONS, PEP AND ADVERSE MEDIA",
    items: [
      { type: "standard_screening_check", label: "Standard AML Screening", desc: "Screen against sanctions & PEP." },
      { type: "extensive_screening_check", label: "Extensive AML Screening", desc: "Deep AML / adverse media." },
    ],
  },
];

export default function WorkflowBuilderPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [wf, setWf] = useState<Workflow | null>(null);
  const [saving, setSaving] = useState(false);
  const [hoverLocked, setHoverLocked] = useState<string | null>(null);

  useEffect(() => {
    api<Workflow>(`/api/workflows/${params.id}`).then(setWf).catch(() => router.replace("/workflows"));
  }, [params.id, router]);

  async function save() {
    if (!wf) return;
    setSaving(true);
    try {
      const updated = await api<Workflow>(`/api/workflows/${wf.id}`, {
        method: "PATCH",
        body: JSON.stringify({ name: wf.name, description: wf.description, steps: wf.steps, status: wf.status }),
      });
      setWf(updated);
    } finally {
      setSaving(false);
    }
  }

  function addStep(type: string, label: string, enabled?: boolean) {
    if (!wf) return;
    if (enabled === false) return;
    setWf({ ...wf, steps: [...wf.steps, { type, label }] });
  }

  if (!wf) {
    return <div className="text-[var(--muted)]">Loading workflow…</div>;
  }

  return (
    <div className="-m-4 md:-m-6 min-h-[calc(100vh-56px)] bg-[#0b0c10]">
      <div className="flex h-14 items-center justify-between border-b border-[var(--border)] px-4">
        <div className="font-semibold">{wf.name} v{wf.version}</div>
        <div className="flex items-center gap-2">
          <button className="grid h-9 w-9 place-items-center rounded-md text-[var(--muted)] hover:bg-[var(--bg-hover)]">
            <Play size={16} />
          </button>
          <button className="grid h-9 w-9 place-items-center rounded-md text-[var(--muted)] hover:bg-[var(--bg-hover)]">
            <HelpCircle size={16} />
          </button>
          <button
            onClick={save}
            disabled={saving}
            className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            <span className="inline-flex items-center gap-1">
              <Save size={14} /> {saving ? "Saving…" : "Save"}
            </span>
          </button>
        </div>
      </div>

      <div className="grid min-h-[calc(100vh-110px)] lg:grid-cols-[280px_1fr_280px]">
        <aside className="border-r border-[var(--border)] p-3 overflow-y-auto max-h-[calc(100vh-110px)]">
          <input
            placeholder="Search check type"
            className="mb-3 w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm outline-none"
          />
          {CATALOG.map((group) => (
            <div key={group.group} className="mb-4">
              <div className="mb-2 text-[10px] font-semibold tracking-wider text-[var(--muted)]">{group.group}</div>
              <div className="space-y-2">
                {group.items.map((item) => {
                  const locked = item.enabled === false || item.enabled === undefined && item.type !== "identity_check" && item.type !== "document_check" && item.type !== "standard_screening_check";
                  return (
                    <button
                      key={item.type}
                      onMouseEnter={() => locked && setHoverLocked(item.type)}
                      onMouseLeave={() => setHoverLocked(null)}
                      onClick={() => addStep(item.type, item.label, !locked)}
                      className={cn(
                        "relative w-full rounded-lg border border-[var(--border)] bg-[var(--bg-panel)] p-3 text-left",
                        locked ? "opacity-50 cursor-not-allowed" : "hover:border-[var(--accent)]",
                      )}
                    >
                      <div className="text-sm font-medium">{item.label}</div>
                      <div className="mt-1 text-xs text-[var(--muted)]">{item.desc}</div>
                      {hoverLocked === item.type ? (
                        <div className="absolute inset-x-2 top-full z-10 mt-1 rounded-md bg-[#111] border border-[var(--border)] p-2 text-xs text-[var(--muted)] shadow-xl">
                          This feature is not enabled for your account. Contact us to find out more.
                        </div>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </aside>

        <section className="relative flex flex-col items-center gap-0 py-10">
          <Node label="START" tone="start" />
          <Connector />
          {wf.steps.map((step, idx) => (
            <div key={`${step.type}-${idx}`} className="flex flex-col items-center">
              <button
                onClick={() => setWf({ ...wf, steps: wf.steps.filter((_, i) => i !== idx) })}
                className="w-56 rounded-xl border-2 border-[var(--accent)] bg-[var(--bg-panel)] px-4 py-4 text-center shadow-[0_0_0_4px_rgba(16,185,129,0.12)]"
                title="Click to remove"
              >
                <div className="mx-auto mb-2 grid h-10 w-10 place-items-center rounded-full bg-[var(--accent-soft)] text-[var(--accent)]">
                  ◉
                </div>
                <div className="font-semibold">{step.label}</div>
              </button>
              <Connector />
            </div>
          ))}
          <Node label="FINISH" tone="finish" />
        </section>

        <aside className="border-l border-[var(--border)] p-4 space-y-4 overflow-y-auto max-h-[calc(100vh-110px)]">
          <div>
            <div className="text-xs text-[var(--muted)] mb-1">WORKFLOW STATUS</div>
            <Badge tone="success">ACTIVE</Badge>
          </div>
          <Field label="WORKFLOW NAME" value={wf.name} onChange={(v) => setWf({ ...wf, name: v })} />
          <div>
            <div className="text-xs text-[var(--muted)] mb-1">WORKFLOW VERSION</div>
            <div>{wf.version}</div>
          </div>
          <div>
            <div className="text-xs text-[var(--muted)] mb-1">WORKFLOW VERSION ID</div>
            <div className="break-all font-mono text-xs text-[var(--muted)]">{wf.id}</div>
          </div>
          <div>
            <div className="text-xs text-[var(--muted)] mb-1">LAST UPDATED</div>
            <div className="text-sm">{formatDate(wf.updated_at)}</div>
          </div>
          <div>
            <div className="text-xs text-[var(--muted)] mb-1">COMPATIBILITY</div>
            <div className="text-sm text-[var(--muted)]">iOS 13+, Android 5+, Web (Chrome, Edge, Firefox, Safari)</div>
          </div>
          <div>
            <div className="text-xs text-[var(--muted)] mb-1">COMPLIANCE POLICIES</div>
            <div className="text-sm text-[var(--muted)]">You currently have 0 active policies.</div>
          </div>
          <Link href="/workflows" className="inline-block text-sm text-[var(--accent)] hover:underline">
            ← Back to workflows
          </Link>
        </aside>
      </div>
    </div>
  );
}

function Node({ label, tone }: { label: string; tone: "start" | "finish" }) {
  return (
    <div
      className={cn(
        "grid h-16 w-16 place-items-center rounded-full border text-xs font-semibold",
        tone === "start"
          ? "border-[var(--border)] bg-[var(--bg-panel)]"
          : "border-[var(--border)] bg-[#22262f]",
      )}
    >
      {label}
    </div>
  );
}

function Connector() {
  return <div className="h-8 w-px bg-[var(--border)]" />;
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="block">
      <div className="text-xs text-[var(--muted)] mb-1">{label}</div>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
      />
    </label>
  );
}
