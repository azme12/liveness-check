"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge, PageHeader, Panel } from "@/components/AppShell";
import { EnvBanner } from "@/components/EnvBanner";
import { api } from "@/lib/api";
import { useEnvironment } from "@/lib/environment";

type MobileInfo = {
  org_id: string;
  environment: string;
  verify_url_pattern: string;
  message: string;
};

export default function MobileAppPage() {
  const { env, label } = useEnvironment();
  const [info, setInfo] = useState<MobileInfo | null>(null);

  const load = useCallback(() => {
    api<MobileInfo>(`/api/integration/mobile?environment=${env}`)
      .then(setInfo)
      .catch(console.error);
  }, [env]);

  useEffect(() => {
    load();
  }, [load]);

  const hosted = typeof window !== "undefined" ? window.location.origin : "";
  const httpsHint = hosted ? `${hosted}/verify/vfy_YOUR_TOKEN` : "/verify/vfy_YOUR_TOKEN";
  const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(httpsHint)}`;

  return (
    <div>
      <PageHeader
        title="Phone verification"
        description="Send clients the hosted verify link to complete document + selfie capture on their phone."
      />
      <EnvBanner noun="hosted verify links" />
      <Panel className="flex flex-wrap items-center gap-8 p-8">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={qrUrl} alt="Mobile verify QR example" className="rounded-lg bg-white p-3" width={220} height={220} />
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex items-center gap-2">
            <h2 className="text-xl font-semibold">Continue on phone</h2>
            <Badge tone={env === "live" ? "live" : "sandbox"}>{label}</Badge>
          </div>
          <p className="mt-2 max-w-md text-sm text-[var(--muted)]">
            {info?.message ||
              "Start verification from a client, choose phone or link, then open /verify/{token} on the device."}
          </p>
          <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Hosted verify URL pattern
          </p>
          <code className="mt-1 block break-all font-mono text-xs text-[var(--muted)]">{httpsHint}</code>
        </div>
      </Panel>
    </div>
  );
}
