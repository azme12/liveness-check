"use client";

import { Panel } from "@/components/AppShell";

export default function SecuritySettingsPage() {
  return (
    <div>
      <div className="mb-4">
        <h2 className="text-xl font-semibold">Security</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Password and session security for your Trustanova account.
        </p>
      </div>
      <Panel className="space-y-4 p-5">
        <div>
          <p className="text-sm font-medium">Password</p>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Demo accounts use a fixed password. Contact your admin to rotate credentials in
            production.
          </p>
        </div>
        <div className="border-t border-[var(--border)] pt-4">
          <p className="text-sm font-medium">Two-factor authentication</p>
          <p className="mt-1 text-sm text-[var(--muted)]">Coming soon for self-hosted deployments.</p>
        </div>
        <div className="border-t border-[var(--border)] pt-4">
          <p className="text-sm font-medium">Active sessions</p>
          <p className="mt-1 text-sm text-[var(--muted)]">
            You are signed in on this browser. Sign out from the profile menu to end the session.
          </p>
        </div>
      </Panel>
    </div>
  );
}
