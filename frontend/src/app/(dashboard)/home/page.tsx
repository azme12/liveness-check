"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Panel } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useEnvironment } from "@/lib/environment";

type Overview = {
  flagged: {
    sessions: Record<string, number>;
    checks: Record<string, number>;
  };
  usage: Array<{
    month: string;
    identity_check: number;
    document_check: number;
    extensive_aml: number;
  }>;
  population: { total: number; persons: number; companies: number };
};

export default function HomePage() {
  const { env, label } = useEnvironment();
  const [data, setData] = useState<Overview | null>(null);

  useEffect(() => {
    api<Overview>(`/api/overview?environment=${env}`).then(setData).catch(console.error);
  }, [env]);

  const cols = [
    ["today", "Today"],
    ["d7", "Last 7 days"],
    ["d30", "Last 30 days"],
    ["d90", "Last 90 days"],
    ["over90", "Over 90 days"],
  ] as const;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <h1 className="text-2xl font-semibold">Activity overview</h1>
        <p className="text-sm text-[var(--muted)]">
          Showing <strong className="text-[var(--text)]">{label}</strong> environment
        </p>
      </div>

      <Panel className="overflow-hidden">
        <div className="border-b border-[var(--border)] px-4 py-3 font-medium">Flagged activity</div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-[var(--muted)]">
              <tr className="border-b border-[var(--border)]">
                <th className="px-4 py-3 text-left font-medium">Type</th>
                {cols.map(([, label]) => (
                  <th key={label} className="px-4 py-3 text-left font-medium">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-[var(--border)]">
                <td className="px-4 py-3">Sessions</td>
                {cols.map(([key]) => (
                  <td key={key} className="px-4 py-3 text-[var(--success)]">
                    {data?.flagged.sessions[key] ?? 0}
                  </td>
                ))}
              </tr>
              <tr>
                <td className="px-4 py-3">Checks</td>
                {cols.map(([key]) => (
                  <td key={key} className="px-4 py-3 text-[var(--warning)]">
                    {data?.flagged.checks[key] ?? 0}
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel className="p-4">
        <div className="mb-3 font-medium">Check usage over 12 months</div>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data?.usage || []}>
              <CartesianGrid stroke="#2a2f3a" strokeDasharray="3 3" />
              <XAxis dataKey="month" stroke="#9aa3b2" />
              <YAxis stroke="#9aa3b2" />
              <Tooltip
                contentStyle={{ background: "#1a1d24", border: "1px solid #2a2f3a" }}
              />
              <Legend />
              <Line type="monotone" dataKey="extensive_aml" name="Extensive AML screening" stroke="#10b981" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="document_check" name="Document check" stroke="#34d399" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="identity_check" name="Identity check" stroke="#f59e0b" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      <Panel className="p-4">
        <div className="mb-3 font-medium">Client population breakdown</div>
        <div className="flex flex-wrap gap-10">
          <Stat label="Total" value={data?.population.total ?? 0} accent />
          <Stat label="Persons" value={data?.population.persons ?? 0} />
          <Stat label="Companies" value={data?.population.companies ?? 0} />
        </div>
      </Panel>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div>
      <div className="text-sm text-[var(--muted)]">{label}</div>
      <div className={`text-3xl font-semibold ${accent ? "text-[var(--accent)]" : ""}`}>
        {value.toLocaleString()}
      </div>
    </div>
  );
}
