"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { HelpCircle, Play, Save } from "lucide-react";
import { DragEvent, useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/AppShell";
import { api } from "@/lib/api";
import { cn, formatDate } from "@/lib/format";

type Step = { type: string; label: string };
type Version = {
  id: string;
  version: number;
  description: string;
  status: string;
  steps: Step[];
  updated_at: string;
};
type Payload = {
  workflow: { id: string; name: string; description: string; status: string };
  version: Version;
};

const CATALOG = [
  {
    group: "SANCTIONS, PEP AND ADVERSE MEDIA",
    items: [
      { type: "standard_screening_check", label: "Standard AML Screening", desc: "Screen against sanctions & PEP.", enabled: true },
      { type: "extensive_screening_check", label: "Extensive AML Screening", desc: "Deep AML / adverse media.", enabled: true },
    ],
  },
  {
    group: "GOVERNMENT ID VERIFICATION",
    items: [{ type: "document_check", label: "Document Check", desc: "Verify government-issued ID.", enabled: true }],
  },
  {
    group: "BIOMETRIC & LIVENESS CHECK",
    items: [
      { type: "identity_check", label: "Identity Check", desc: "Biometric & liveness verification (selfie).", enabled: true },
      { type: "enhanced_identity_check", label: "Enhanced Identity Check", desc: "Biometric & liveness verification (video).", enabled: true },
      { type: "age_estimation_check", label: "Age Estimation Check", desc: "Estimate client age from selfie.", enabled: true },
    ],
  },
  {
    group: "ADDRESS & IDENTITY DATA CHECK",
    items: [
      { type: "multi_bureau_check", label: "Multi Bureau Check", desc: "Verify client details via trusted sources.", enabled: true },
      { type: "proof_of_address_check", label: "Proof of Address Check", desc: "Verify POA documents.", enabled: true },
    ],
  },
];

export default function WorkflowEditorPage() {
  const params = useParams<{ id: string; versionId: string }>();
  const router = useRouter();
  const [data, setData] = useState<Payload | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [description, setDescription] = useState("");
  const [status, setStatus] = useState("inactive");
  const [saving, setSaving] = useState(false);
  const [catalogQ, setCatalogQ] = useState("");
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  useEffect(() => {
    api<Payload>(`/api/workflows/${params.id}/versions/${params.versionId}`)
      .then((res) => {
        setData(res);
        setSteps(res.version.steps || []);
        setDescription(res.version.description || "");
        setStatus(res.version.status || "inactive");
      })
      .catch(() => router.replace("/workflows"));
  }, [params.id, params.versionId, router]);

  const filteredCatalog = useMemo(() => {
    const q = catalogQ.trim().toLowerCase();
    if (!q) return CATALOG;
    return CATALOG.map((g) => ({
      ...g,
      items: g.items.filter(
        (i) => i.label.toLowerCase().includes(q) || i.type.toLowerCase().includes(q),
      ),
    })).filter((g) => g.items.length > 0);
  }, [catalogQ]);

  function addStep(type: string, label: string) {
    setSteps((prev) => [...prev, { type, label }]);
  }

  function onDragStart(index: number) {
    setDragIndex(index);
  }

  function onDragOver(e: DragEvent, index: number) {
    e.preventDefault();
    if (dragIndex === null || dragIndex === index) return;
    setSteps((prev) => {
      const next = [...prev];
      const [item] = next.splice(dragIndex, 1);
      next.splice(index, 0, item);
      return next;
    });
    setDragIndex(index);
  }

  function onCatalogDrop(e: DragEvent) {
    e.preventDefault();
    const raw = e.dataTransfer.getData("application/workflow-check");
    if (!raw) return;
    try {
      const item = JSON.parse(raw) as Step;
      if (item.type && item.label) addStep(item.type, item.label);
    } catch {
      /* ignore */
    }
  }

  async function save() {
    if (!data) return;
    setSaving(true);
    try {
      const updated = await api<Version>(
        `/api/workflows/${params.id}/versions/${params.versionId}`,
        {
          method: "PATCH",
          body: JSON.stringify({ steps, description, status }),
        },
      );
      setData({ ...data, version: updated });
      setStatus(updated.status);
    } finally {
      setSaving(false);
    }
  }

  if (!data) {
    return <div className="text-[var(--muted)]">Loading editor…</div>;
  }

  const { workflow, version } = data;

  return (
    <div className="-m-4 md:-m-6 min-h-[calc(100vh-56px)] bg-[#0b0c10]">
      <div className="flex h-14 items-center justify-between border-b border-[var(--border)] px-4">
        <div className="font-semibold">
          {workflow.name} v{version.version}
        </div>
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
        <aside className="max-h-[calc(100vh-110px)] overflow-y-auto border-r border-[var(--border)] p-3">
          <input
            value={catalogQ}
            onChange={(e) => setCatalogQ(e.target.value)}
            placeholder="Search check type"
            className="mb-3 w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm outline-none"
          />
          <p className="mb-3 text-[11px] text-[var(--muted)]">Drag a check onto the canvas, or click to add.</p>
          {filteredCatalog.map((group) => (
            <div key={group.group} className="mb-4">
              <div className="mb-2 text-[10px] font-semibold tracking-wider text-[var(--muted)]">{group.group}</div>
              <div className="space-y-2">
                {group.items.map((item) => (
                  <button
                    key={item.type}
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData(
                        "application/workflow-check",
                        JSON.stringify({ type: item.type, label: item.label }),
                      );
                      e.dataTransfer.effectAllowed = "copy";
                    }}
                    onClick={() => addStep(item.type, item.label)}
                    className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg-panel)] p-3 text-left hover:border-[var(--accent)]"
                  >
                    <div className="text-sm font-medium">{item.label}</div>
                    <div className="mt-1 text-xs text-[var(--muted)]">{item.desc}</div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </aside>

        <section
          className="relative flex flex-col items-center gap-0 py-10"
          onDragOver={(e) => e.preventDefault()}
          onDrop={onCatalogDrop}
        >
          <Node label="START" tone="start" />
          <Connector />
          {steps.length === 0 ? (
            <div className="mb-2 w-64 rounded-xl border border-dashed border-[var(--border)] px-4 py-8 text-center text-sm text-[var(--muted)]">
              Drop checks here
            </div>
          ) : null}
          {steps.map((step, idx) => (
            <div key={`${step.type}-${idx}`} className="flex flex-col items-center">
              <div
                draggable
                onDragStart={() => onDragStart(idx)}
                onDragOver={(e) => onDragOver(e, idx)}
                onDragEnd={() => setDragIndex(null)}
                className={cn(
                  "w-56 cursor-grab rounded-xl border-2 border-[var(--accent)] bg-[var(--bg-panel)] px-4 py-4 text-center shadow-[0_0_0_4px_rgba(59,130,246,0.12)] active:cursor-grabbing",
                  dragIndex === idx && "opacity-70",
                )}
              >
                <div className="mx-auto mb-2 grid h-10 w-10 place-items-center rounded-full bg-[var(--accent-soft)] text-[var(--accent)]">
                  ◉
                </div>
                <div className="font-semibold">{step.label}</div>
                <button
                  type="button"
                  onClick={() => setSteps((prev) => prev.filter((_, i) => i !== idx))}
                  className="mt-2 text-xs text-[var(--danger)] hover:underline"
                >
                  Remove
                </button>
              </div>
              <Connector />
            </div>
          ))}
          <Node label="FINISH" tone="finish" />
        </section>

        <aside className="max-h-[calc(100vh-110px)] space-y-4 overflow-y-auto border-l border-[var(--border)] p-4">
          <div>
            <div className="mb-1 text-xs text-[var(--muted)]">WORKFLOW STATUS</div>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="rounded-md border border-[var(--border)] bg-[var(--bg)] px-2 py-1.5 text-sm outline-none"
            >
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
            <div className="mt-2">
              {status === "active" ? <Badge tone="success">ACTIVE</Badge> : <Badge>INACTIVE</Badge>}
            </div>
          </div>
          <div>
            <div className="mb-1 text-xs text-[var(--muted)]">WORKFLOW NAME</div>
            <div className="text-sm">{workflow.name}</div>
          </div>
          <div>
            <div className="mb-1 text-xs text-[var(--muted)]">WORKFLOW VERSION</div>
            <div>{version.version}</div>
          </div>
          <div>
            <div className="mb-1 text-xs text-[var(--muted)]">WORKFLOW VERSION ID</div>
            <div className="break-all font-mono text-xs text-[var(--muted)]">{version.id}</div>
          </div>
          <label className="block">
            <div className="mb-1 text-xs text-[var(--muted)]">VERSION DESCRIPTION</div>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-sm outline-none focus:border-[var(--accent)]"
            />
          </label>
          <div>
            <div className="mb-1 text-xs text-[var(--muted)]">LAST UPDATED</div>
            <div className="text-sm">{formatDate(version.updated_at)}</div>
          </div>
          <div>
            <div className="mb-1 text-xs text-[var(--muted)]">COMPATIBILITY</div>
            <div className="text-sm text-[var(--muted)]">iOS 13+, Android 5+, Web (Chrome, Edge, Firefox, Safari)</div>
          </div>
          <Link href={`/workflows/${workflow.id}`} className="inline-block text-sm text-[var(--accent)] hover:underline">
            ← Back to versions
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
        tone === "start" ? "border-[var(--border)] bg-[var(--bg-panel)]" : "border-[var(--border)] bg-[#22262f]",
      )}
    >
      {label}
    </div>
  );
}

function Connector() {
  return <div className="h-8 w-px bg-[var(--border)]" />;
}
