"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Filter, Plus, RefreshCw, Trash2, Upload } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Panel, ToolbarSearch } from "@/components/AppShell";
import { Footer } from "@/components/Footer";
import { api, Paginated } from "@/lib/api";
import { useEnvironment } from "@/lib/environment";
import { cn, formatDate } from "@/lib/format";

type Client = {
  id: string;
  name: string;
  email?: string | null;
  risk: string;
  type: string;
  created_at: string;
};

export default function ClientsPage() {
  const router = useRouter();
  const { env } = useEnvironment();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [data, setData] = useState<Paginated<Client> | null>(null);
  const [open, setOpen] = useState(false);
  const [type, setType] = useState<"person" | "company">("person");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [email, setEmail] = useState("");
  const [mobile, setMobile] = useState("");
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const [confirm, setConfirm] = useState<{ mode: "single" | "bulk"; ids: string[]; name?: string } | null>(
    null,
  );

  const load = useCallback(() => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
      environment: env,
    });
    if (q.trim().length >= 3) params.set("q", q.trim());
    api<Paginated<Client>>(`/api/clients?${params}`)
      .then((res) => {
        setData(res);
        setSelected((prev) => {
          const ids = new Set(res.items.map((c) => c.id));
          return new Set([...prev].filter((id) => ids.has(id)));
        });
      })
      .catch(console.error);
  }, [page, pageSize, q, env]);

  useEffect(() => {
    load();
  }, [load]);

  const pageIds = useMemo(() => (data?.items || []).map((c) => c.id), [data]);
  const allSelected = pageIds.length > 0 && pageIds.every((id) => selected.has(id));
  const someSelected = pageIds.some((id) => selected.has(id));

  function toggleOne(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setSelected((prev) => {
      if (allSelected) {
        const next = new Set(prev);
        pageIds.forEach((id) => next.delete(id));
        return next;
      }
      const next = new Set(prev);
      pageIds.forEach((id) => next.add(id));
      return next;
    });
  }

  async function runDelete(ids: string[]) {
    setDeleting(true);
    setError("");
    try {
      if (ids.length === 1) {
        await api(`/api/clients/${ids[0]}`, { method: "DELETE" });
      } else {
        await api("/api/clients/bulk-delete", {
          method: "POST",
          body: JSON.stringify({ ids }),
        });
      }
      setSelected((prev) => {
        const next = new Set(prev);
        ids.forEach((id) => next.delete(id));
        return next;
      });
      setConfirm(null);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setDeleting(false);
    }
  }

  async function onAdd(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const created = await api<Client>("/api/clients", {
        method: "POST",
        body: JSON.stringify({
          type,
          first_name: type === "person" ? firstName : null,
          last_name: type === "person" ? lastName : null,
          company_name: type === "company" ? companyName : null,
          email: email || null,
          mobile: mobile || null,
        }),
      });
      setOpen(false);
      setFirstName("");
      setLastName("");
      setCompanyName("");
      setEmail("");
      setMobile("");
      router.push(`/clients/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    }
  }

  return (
    <div>
      <p className="mb-4 text-sm text-[var(--muted)]">
        A client is a customer or applicant, either a person or company, on whom you can perform checks or run through a
        verification flow.
      </p>
      <ToolbarSearch
        value={q}
        onChange={(v) => {
          setPage(1);
          setQ(v);
        }}
        placeholder="Search by client name, email or ID (min 3 characters)."
        actions={
          <>
            <IconAction onClick={load} icon={<RefreshCw size={16} />} />
            <IconAction icon={<Filter size={16} />} />
            {selected.size > 0 ? (
              <button
                type="button"
                onClick={() => setConfirm({ mode: "bulk", ids: [...selected] })}
                className="inline-flex items-center gap-1 rounded-lg border border-[var(--danger)]/40 bg-[rgba(239,68,68,0.12)] px-3 py-2 text-sm font-semibold text-[var(--danger)]"
              >
                <Trash2 size={16} /> Delete ({selected.size})
              </button>
            ) : null}
            <button
              onClick={() => setOpen(true)}
              className="inline-flex items-center gap-1 rounded-lg bg-[var(--accent)] px-3 py-2 text-sm font-semibold text-white"
            >
              <Plus size={16} /> Add client
            </button>
            <button className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] px-3 py-2 text-sm text-[var(--muted)]">
              <Upload size={16} /> Export
            </button>
          </>
        }
      />

      <Panel className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-[var(--muted)]">
              <tr className="border-b border-[var(--border)]">
                <th className="w-10 px-4 py-3">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    ref={(el) => {
                      if (el) el.indeterminate = someSelected && !allSelected;
                    }}
                    onChange={toggleAll}
                    aria-label="Select all clients on this page"
                    className="h-4 w-4 accent-[var(--accent)]"
                  />
                </th>
                <th className="px-4 py-3 text-left font-medium">Name</th>
                <th className="px-4 py-3 text-left font-medium">Email</th>
                <th className="px-4 py-3 text-left font-medium">Risk</th>
                <th className="px-4 py-3 text-left font-medium">Type</th>
                <th className="px-4 py-3 text-left font-medium">Added</th>
                <th className="px-4 py-3 text-right font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {(data?.items || []).map((c) => {
                const isOn = selected.has(c.id);
                return (
                  <tr
                    key={c.id}
                    className={cn(
                      "border-b border-[var(--border)] last:border-0 hover:bg-[var(--bg-hover)]",
                      isOn && "bg-[var(--accent-soft)]/30",
                    )}
                  >
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={isOn}
                        onChange={() => toggleOne(c.id)}
                        aria-label={`Select ${c.name}`}
                        className="h-4 w-4 accent-[var(--accent)]"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/clients/${c.id}`} className="flex items-center gap-2 hover:text-[var(--accent)]">
                        <span className="grid h-8 w-8 place-items-center rounded-full bg-[var(--bg-hover)] text-xs">
                          {c.name.slice(0, 1)}
                        </span>
                        <span className="font-medium">{c.name}</span>
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-[var(--muted)]">{c.email || "—"}</td>
                    <td className="px-4 py-3">
                      <Badge tone="success">{c.risk === "low" ? "Low" : c.risk}</Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge>{c.type === "person" ? "Person" : "Company"}</Badge>
                    </td>
                    <td className="px-4 py-3 text-[var(--muted)]">{formatDate(c.created_at)}</td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        title="Delete client"
                        onClick={() => setConfirm({ mode: "single", ids: [c.id], name: c.name })}
                        className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[var(--muted)] hover:bg-[rgba(239,68,68,0.12)] hover:text-[var(--danger)]"
                      >
                        <Trash2 size={15} />
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <Footer
          total={data?.total || 0}
          page={page}
          pages={data?.pages || 1}
          pageSize={pageSize}
          onPage={setPage}
          onPageSize={(n) => {
            setPage(1);
            setPageSize(n);
          }}
        />
      </Panel>

      {open ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <form onSubmit={onAdd} className="w-full max-w-lg rounded-xl border border-[var(--border)] bg-[var(--bg-panel)] p-5">
            <h2 className="mb-4 text-xl font-semibold">Add client</h2>
            <div className="mb-4 flex gap-4 text-sm">
              <label className="inline-flex items-center gap-2">
                <input type="radio" checked={type === "person"} onChange={() => setType("person")} />
                PERSON
              </label>
              <label className="inline-flex items-center gap-2">
                <input type="radio" checked={type === "company"} onChange={() => setType("company")} />
                COMPANY
              </label>
            </div>
            {type === "person" ? (
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="First Name*" value={firstName} onChange={setFirstName} placeholder="e.g. John" required />
                <Field label="Last Name*" value={lastName} onChange={setLastName} placeholder="e.g. Doe" required />
              </div>
            ) : (
              <Field
                label="Company Name*"
                value={companyName}
                onChange={setCompanyName}
                placeholder="e.g. Acme Ltd"
                required
              />
            )}
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field
                label="Email Address*"
                value={email}
                onChange={setEmail}
                placeholder="e.g. john.doe@example.com"
                type="email"
                required
              />
              <Field label="Mobile" value={mobile} onChange={setMobile} placeholder="e.g. +2519…" />
            </div>
            {error ? <p className="mt-3 text-sm text-[var(--danger)]">{error}</p> : null}
            <div className="mt-5 flex justify-end gap-2">
              <button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-[var(--border)] px-4 py-2">
                Cancel
              </button>
              <button type="submit" className="rounded-lg bg-[var(--success)] px-4 py-2 font-semibold text-black">
                Add client
              </button>
            </div>
          </form>
        </div>
      ) : null}

      {confirm ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--bg-panel)] p-5">
            <h2 className="text-lg font-semibold">Delete client{confirm.ids.length > 1 ? "s" : ""}?</h2>
            <p className="mt-2 text-sm text-[var(--muted)]">
              {confirm.mode === "single"
                ? `This will permanently delete “${confirm.name || "this client"}”.`
                : `This will permanently delete ${confirm.ids.length} selected clients.`}
            </p>
            {error ? <p className="mt-3 text-sm text-[var(--danger)]">{error}</p> : null}
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                disabled={deleting}
                onClick={() => {
                  setConfirm(null);
                  setError("");
                }}
                className="rounded-lg border border-[var(--border)] px-4 py-2"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deleting}
                onClick={() => runDelete(confirm.ids)}
                className="rounded-lg bg-[var(--danger)] px-4 py-2 font-semibold text-white disabled:opacity-60"
              >
                {deleting ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
  required?: boolean;
}) {
  return (
    <label className="block text-sm">
      <span className="text-[var(--muted)]">{label}</span>
      <input
        className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none focus:border-[var(--accent)]"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        type={type}
        required={required}
      />
    </label>
  );
}

function IconAction({ icon, onClick }: { icon: React.ReactNode; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="grid h-10 w-10 place-items-center rounded-lg border border-[var(--border)] text-[var(--muted)] hover:bg-[var(--bg-hover)]"
    >
      {icon}
    </button>
  );
}
