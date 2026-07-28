"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Copy, Filter, Plus, RefreshCw } from "lucide-react";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Badge, Panel, ToolbarSearch } from "@/components/AppShell";
import { Footer } from "@/components/Footer";
import { api, Paginated } from "@/lib/api";
import { useEnvironment } from "@/lib/environment";
import { formatDate } from "@/lib/format";
import { useDebouncedValue } from "@/lib/useDebouncedValue";

type Workflow = {
  id: string;
  name: string;
  description: string;
  status: string;
  updated_at: string;
};

export default function WorkflowsPage() {
  const router = useRouter();
  const { env } = useEnvironment();
  const [q, setQ] = useState("");
  const debouncedQ = useDebouncedValue(q, 350);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paginated<Workflow> | null>(null);
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    const params = new URLSearchParams({ page: String(page), page_size: "10", environment: env });
    if (debouncedQ.trim().length >= 3) params.set("q", debouncedQ.trim());
    api<Paginated<Workflow>>(`/api/workflows?${params}`).then(setData).catch(console.error);
  }, [page, debouncedQ, env]);

  useEffect(() => {
    load();
  }, [load]);

  async function createWorkflow(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) {
      setError("Name is required");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const created = await api<Workflow>("/api/workflows", {
        method: "POST",
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim(),
          steps: [{ type: "identity_check", label: "Identity Check" }],
        }),
      });
      setOpen(false);
      setName("");
      setDescription("");
      router.push(`/workflows/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create workflow");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <p className="mb-4 text-sm text-[var(--muted)]">
        A workflow is a reusable set of verification steps that you apply when verifying clients.
      </p>
      <ToolbarSearch
        value={q}
        onChange={(v) => {
          setPage(1);
          setQ(v);
        }}
        placeholder="Search by template name or ID (min 3 characters)"
        actions={
          <>
            <button onClick={load} className="grid h-10 w-10 place-items-center rounded-lg border border-[var(--border)] text-[var(--muted)]">
              <RefreshCw size={16} />
            </button>
            <button className="grid h-10 w-10 place-items-center rounded-lg border border-[var(--border)] text-[var(--muted)]">
              <Filter size={16} />
            </button>
            <button
              onClick={() => setOpen(true)}
              className="inline-flex items-center gap-1 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-semibold text-white"
            >
              <Plus size={16} /> New workflow
            </button>
          </>
        }
      />
      <Panel className="overflow-hidden">
        <table className="w-full text-sm">
          <thead className="text-[var(--muted)]">
            <tr className="border-b border-[var(--border)]">
              <th className="px-4 py-3 text-left font-medium">Workflow name</th>
              <th className="px-4 py-3 text-left font-medium">Description</th>
              <th className="px-4 py-3 text-left font-medium">Status</th>
              <th className="px-4 py-3 text-left font-medium">Last updated</th>
            </tr>
          </thead>
          <tbody>
            {(data?.items || []).map((w) => (
              <tr
                key={w.id}
                className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-hover)]"
              >
                <td className="px-4 py-3">
                  <Link
                    href={`/workflows/${w.id}`}
                    className="block font-medium text-[var(--accent)] underline underline-offset-2 hover:text-white"
                  >
                    {w.name}
                  </Link>
                  <div className="mt-1 flex items-center gap-1 font-mono text-xs text-[var(--muted)]">
                    ID: {w.id}
                    <button
                      type="button"
                      onClick={() => navigator.clipboard.writeText(w.id)}
                      className="hover:text-white"
                      title="Copy ID"
                    >
                      <Copy size={12} />
                    </button>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <Link href={`/workflows/${w.id}`} className="block text-[var(--muted)] hover:text-white">
                    {w.description || "—"}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <Link href={`/workflows/${w.id}`} className="inline-block">
                    {w.status === "active" ? (
                      <Badge tone="success">Active</Badge>
                    ) : (
                      <Badge>Inactive</Badge>
                    )}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  <Link href={`/workflows/${w.id}`} className="block text-[var(--muted)] hover:text-white">
                    {formatDate(w.updated_at)}
                  </Link>
                </td>
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

      {open ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <form
            onSubmit={createWorkflow}
            className="w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--bg-panel)] p-5"
          >
            <h2 className="mb-4 text-xl font-semibold">New workflow</h2>
            <label className="mb-3 block text-sm">
              <span className="text-[var(--muted)]">Name*</span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none focus:border-[var(--accent)]"
                placeholder="e.g. Full KYC"
                required
              />
            </label>
            <label className="block text-sm">
              <span className="text-[var(--muted)]">Description</span>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none focus:border-[var(--accent)]"
                placeholder="What this workflow verifies…"
              />
            </label>
            {error ? <p className="mt-3 text-sm text-[var(--danger)]">{error}</p> : null}
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setOpen(false);
                  setError("");
                }}
                className="rounded-lg border border-[var(--border)] px-4 py-2"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-[var(--success)] px-4 py-2 font-semibold text-black disabled:opacity-60"
              >
                {saving ? "Creating…" : "Create workflow"}
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}
