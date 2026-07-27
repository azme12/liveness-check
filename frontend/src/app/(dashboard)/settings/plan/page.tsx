"use client";

import { Badge, Panel } from "@/components/AppShell";

export default function PlanSettingsPage() {
  return (
    <div>
      <div className="mb-4">
        <h2 className="text-xl font-semibold">Plan</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Your current Trustanova workspace plan.</p>
      </div>
      <Panel className="p-5">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-lg font-semibold">Self-hosted</h3>
          <Badge tone="live">Active</Badge>
        </div>
        <p className="mt-2 max-w-xl text-sm text-[var(--muted)]">
          Unlimited clients, checks, and webhooks for this local deployment. Upgrade paths and
          billing are not required for open-source self-hosting.
        </p>
        <ul className="mt-4 space-y-2 text-sm text-[var(--muted)]">
          <li>• Dashboard users: unlimited</li>
          <li>• API rate limits: configurable per key</li>
          <li>• Webhook delivery: included</li>
        </ul>
      </Panel>
    </div>
  );
}
