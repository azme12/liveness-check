"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge, PageHeader, Panel } from "@/components/AppShell";
import { EnvBanner } from "@/components/EnvBanner";
import { api } from "@/lib/api";
import { useEnvironment } from "@/lib/environment";

type MobileInfo = {
  org_id: string;
  environment: string;
  qr_payload: string;
  message: string;
  web_sdk_key?: { key: string } | null;
};

export default function MobileAppPage() {
  const { env, label } = useEnvironment();
  const [info, setInfo] = useState<MobileInfo | null>(null);
  const [reveal, setReveal] = useState(false);

  const load = useCallback(() => {
    api<MobileInfo>(`/api/integration/mobile?environment=${env}`)
      .then(setInfo)
      .catch(console.error);
  }, [env]);

  useEffect(() => {
    setReveal(false);
    load();
  }, [load]);

  const payload = info?.qr_payload || "trustanova://link";
  const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(payload)}`;
  const pk = info?.web_sdk_key?.key || "";

  return (
    <div>
      <PageHeader
        title="Mobile SDK"
        description={`Link devices using the ${label} environment publishable key.`}
      />
      <EnvBanner noun="mobile SDK links" />
      <Panel className="flex flex-wrap items-center gap-8 p-8">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={qrUrl} alt="Mobile link QR" className="rounded-lg bg-white p-3" width={220} height={220} />
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex items-center gap-2">
            <h2 className="text-xl font-semibold">Scan with your device</h2>
            <Badge tone={env === "live" ? "live" : "sandbox"}>{label}</Badge>
          </div>
          <p className="mt-2 max-w-md text-sm text-[var(--muted)]">
            {info?.message ||
              "Link it to your Trustanova account to test capture flows on iOS and Android."}
          </p>
          <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Web SDK key ({env === "test" ? "pk_test_*" : "pk_live_*"})
          </p>
          <code className="mt-1 block break-all font-mono text-xs text-[var(--muted)]">
            {reveal ? pk || "—" : "pk_••••••••••••••••"}
          </code>
          <button
            type="button"
            onClick={() => setReveal((v) => !v)}
            className="mt-2 text-sm text-[var(--accent)] hover:underline"
          >
            {reveal ? "Hide key" : "Reveal key"}
          </button>
          <p className="mt-4 font-mono text-xs text-[var(--muted)] break-all">{payload}</p>
        </div>
      </Panel>
    </div>
  );
}
