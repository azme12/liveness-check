"use client";

import { useEffect, useState } from "react";
import { Panel } from "@/components/AppShell";
import { api } from "@/lib/api";

type Prefs = {
  email_checks: boolean;
  email_webhooks: boolean;
  in_app: boolean;
};

export default function NotificationSettingsPage() {
  const [prefs, setPrefs] = useState<Prefs>({
    email_checks: true,
    email_webhooks: true,
    in_app: true,
  });
  const [message, setMessage] = useState("");

  useEffect(() => {
    api<{ notification_prefs?: Prefs }>("/api/auth/me")
      .then((data) => {
        if (data.notification_prefs) setPrefs(data.notification_prefs);
      })
      .catch(console.error);
  }, []);

  async function update(key: keyof Prefs, value: boolean) {
    const next = { ...prefs, [key]: value };
    setPrefs(next);
    setMessage("");
    try {
      const data = await api<{ notification_prefs: Prefs }>("/api/auth/notification-prefs", {
        method: "PATCH",
        body: JSON.stringify({ [key]: value }),
      });
      setPrefs(data.notification_prefs);
      setMessage("Preferences saved");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Failed");
    }
  }

  return (
    <div>
      <div className="mb-4">
        <h2 className="text-xl font-semibold">Notifications</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Choose how you want to be notified about checks and webhooks.
        </p>
      </div>
      <Panel className="divide-y divide-[var(--border)]">
        <ToggleRow
          title="In-app notifications"
          description="Show alerts in the notifications panel"
          checked={prefs.in_app}
          onChange={(v) => update("in_app", v)}
        />
        <ToggleRow
          title="Email on check completion"
          description="Email when a verification check completes"
          checked={prefs.email_checks}
          onChange={(v) => update("email_checks", v)}
        />
        <ToggleRow
          title="Email on webhook failures"
          description="Email when webhook delivery fails repeatedly"
          checked={prefs.email_webhooks}
          onChange={(v) => update("email_webhooks", v)}
        />
      </Panel>
      {message ? <p className="mt-3 text-sm text-[var(--success)]">{message}</p> : null}
    </div>
  );
}

function ToggleRow({
  title,
  description,
  checked,
  onChange,
}: {
  title: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-4">
      <div>
        <p className="text-sm font-medium">{title}</p>
        <p className="text-xs text-[var(--muted)]">{description}</p>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-6 w-11 rounded-full transition ${
          checked ? "bg-[var(--accent)]" : "bg-[var(--bg-hover)]"
        }`}
      >
        <span
          className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition ${
            checked ? "left-5" : "left-0.5"
          }`}
        />
      </button>
    </div>
  );
}
