"use client";

import { FormEvent, useEffect, useState } from "react";
import { Panel } from "@/components/AppShell";
import { api, getStoredUser, setSession } from "@/lib/api";

type MeResponse = {
  user: {
    id: string;
    email: string;
    full_name?: string;
    first_name?: string;
    last_name?: string;
  };
};

function gravatarUrl(email: string) {
  // Simple geometric placeholder — Gravatar-style hash not needed for demo
  const seed = encodeURIComponent(email || "user");
  return `https://api.dicebear.com/7.x/shapes/svg?seed=${seed}&backgroundColor=10b981`;
}

export default function AccountSettingsPage() {
  const stored = getStoredUser<{ email?: string; full_name?: string; first_name?: string; last_name?: string }>();
  const [firstName, setFirstName] = useState(stored?.first_name || stored?.full_name?.split(" ")[0] || "");
  const [lastName, setLastName] = useState(
    stored?.last_name || stored?.full_name?.split(" ").slice(1).join(" ") || "",
  );
  const [email, setEmail] = useState(stored?.email || "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<MeResponse>("/api/auth/me")
      .then((data) => {
        setFirstName(data.user.first_name || data.user.full_name?.split(" ")[0] || "");
        setLastName(
          data.user.last_name || data.user.full_name?.split(" ").slice(1).join(" ") || "",
        );
        setEmail(data.user.email || "");
      })
      .catch(console.error);
  }, []);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const data = await api<{ user: MeResponse["user"] }>("/api/auth/profile", {
        method: "PATCH",
        body: JSON.stringify({
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          email: email.trim(),
        }),
      });
      const token = localStorage.getItem("trustanova_token");
      if (token) setSession(token, data.user);
      setMessage("Profile saved");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  function onCancel() {
    setMessage("");
    setError("");
    api<MeResponse>("/api/auth/me")
      .then((data) => {
        setFirstName(data.user.first_name || "");
        setLastName(data.user.last_name || "");
        setEmail(data.user.email || "");
      })
      .catch(console.error);
  }

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-xl font-semibold">Profile</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Update your personal details and profile photo.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <Panel className="p-5">
          <form onSubmit={onSave} className="space-y-4">
            <Field label="First name *">
              <input
                required
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none focus:border-[var(--accent)]"
              />
            </Field>
            <Field label="Last name *">
              <input
                required
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none focus:border-[var(--accent)]"
              />
            </Field>
            <Field label="Email address *">
              <input
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none focus:border-[var(--accent)]"
              />
            </Field>
            {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
            {message ? <p className="text-sm text-[var(--success)]">{message}</p> : null}
            <div className="flex justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={onCancel}
                className="rounded-md border border-[var(--border)] px-3 py-2 text-sm text-[var(--muted)] hover:bg-[var(--bg-hover)]"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-md bg-[var(--accent)] px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                {saving ? "Saving…" : "Save profile"}
              </button>
            </div>
          </form>
        </Panel>

        <Panel className="p-5">
          <h3 className="font-semibold">Update Profile Photo</h3>
          <p className="mt-2 text-sm text-[var(--muted)]">
            Trustanova uses Gravatar-style avatars. Here&apos;s your current one:
          </p>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={gravatarUrl(email)}
            alt="Profile"
            className="mt-4 h-28 w-28 rounded-lg border border-[var(--border)] bg-[var(--bg)]"
          />
          <p className="mt-3 text-sm text-[var(--muted)]">
            Follow the Gravatar instructions to update your avatar using the same email as on
            Trustanova.
          </p>
        </Panel>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
        {label}
      </span>
      {children}
    </label>
  );
}
