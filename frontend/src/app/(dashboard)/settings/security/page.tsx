"use client";

import { FormEvent, useState } from "react";
import { Panel } from "@/components/AppShell";
import { api } from "@/lib/api";

export default function SecuritySettingsPage() {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setOk("");
    if (newPassword !== confirm) {
      setError("New passwords do not match");
      return;
    }
    if (newPassword.length < 6) {
      setError("New password must be at least 6 characters");
      return;
    }
    setLoading(true);
    try {
      await api("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      setOk("Password updated");
      setCurrentPassword("");
      setNewPassword("");
      setConfirm("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to change password");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-xl font-semibold">Security</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Password and session security for your Trustanova account.
        </p>
      </div>
      <Panel className="space-y-4 p-5">
        <form onSubmit={onSubmit} className="space-y-3 max-w-md">
          <p className="text-sm font-medium">Change password</p>
          <label className="block text-sm">
            <span className="text-[var(--muted)]">Current password</span>
            <input
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none focus:border-[var(--accent)]"
              required
            />
          </label>
          <label className="block text-sm">
            <span className="text-[var(--muted)]">New password</span>
            <input
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none focus:border-[var(--accent)]"
              minLength={6}
              required
            />
          </label>
          <label className="block text-sm">
            <span className="text-[var(--muted)]">Confirm new password</span>
            <input
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none focus:border-[var(--accent)]"
              minLength={6}
              required
            />
          </label>
          {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
          {ok ? <p className="text-sm text-[var(--success)]">{ok}</p> : null}
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {loading ? "Saving…" : "Update password"}
          </button>
        </form>
        <div className="border-t border-[var(--border)] pt-4">
          <p className="text-sm font-medium">Two-factor authentication</p>
          <p className="mt-1 text-sm text-[var(--muted)]">Coming soon.</p>
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
