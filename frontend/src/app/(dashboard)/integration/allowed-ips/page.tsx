"use client";

import { Lock, Plus } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { PageHeader, Panel } from "@/components/AppShell";
import { EnvBanner } from "@/components/EnvBanner";
import { api } from "@/lib/api";

type Ip = { id: string; cidr: string; label: string };

export default function AllowedIpsPage() {
  const [items, setItems] = useState<Ip[]>([]);
  const [open, setOpen] = useState(false);
  const [cidr, setCidr] = useState("");
  const [label, setLabel] = useState("");

  async function load() {
    const data = await api<{ items: Ip[] }>("/api/integration/allowed-ips");
    setItems(data.items);
  }

  useEffect(() => {
    load().catch(console.error);
  }, []);

  async function onAdd(e: FormEvent) {
    e.preventDefault();
    await api("/api/integration/allowed-ips", {
      method: "POST",
      body: JSON.stringify({ cidr, label }),
    });
    setOpen(false);
    setCidr("");
    setLabel("");
    await load();
  }

  return (
    <div>
      <PageHeader
        title="Allowed IPs"
        description="Restrict API access to specific IP addresses or CIDR ranges to ensure only trusted sources can connect."
        actions={
          <button
            onClick={() => setOpen(true)}
            className="inline-flex items-center gap-1 rounded-lg border border-[var(--accent)] px-3 py-2 text-sm text-[var(--accent)]"
          >
            <Plus size={16} /> Add IP address
          </button>
        }
      />
      <EnvBanner noun="allowed IP addresses" />
      <Panel className="min-h-[360px]">
        {items.length === 0 ? (
          <div className="grid min-h-[360px] place-items-center text-[var(--muted)]">
            <div className="text-center">
              <Lock className="mx-auto mb-3 opacity-70" size={48} />
              <p>No IP addresses added yet.</p>
            </div>
          </div>
        ) : (
          <ul className="divide-y divide-[var(--border)]">
            {items.map((ip) => (
              <li key={ip.id} className="flex items-center justify-between px-4 py-3 text-sm">
                <div>
                  <div className="font-mono">{ip.cidr}</div>
                  <div className="text-[var(--muted)]">{ip.label || "—"}</div>
                </div>
                <button
                  className="text-[var(--danger)]"
                  onClick={async () => {
                    await api(`/api/integration/allowed-ips/${ip.id}`, { method: "DELETE" });
                    await load();
                  }}
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {open ? (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <form onSubmit={onAdd} className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--bg-panel)] p-5">
            <h2 className="mb-4 text-lg font-semibold">Add IP address</h2>
            <label className="block text-sm mb-3">
              <span className="text-[var(--muted)]">CIDR / IP</span>
              <input
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2"
                value={cidr}
                onChange={(e) => setCidr(e.target.value)}
                placeholder="203.0.113.10/32"
                required
              />
            </label>
            <label className="block text-sm mb-4">
              <span className="text-[var(--muted)]">Label</span>
              <input
                className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="Office VPN"
              />
            </label>
            <div className="flex justify-end gap-2">
              <button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-[var(--border)] px-3 py-2">
                Cancel
              </button>
              <button type="submit" className="rounded-lg bg-[var(--accent)] px-3 py-2 text-white">
                Add
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </div>
  );
}
