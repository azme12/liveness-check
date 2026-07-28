"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

type SessionData = {
  session: {
    id: string;
    client_id: string;
    client_name: string;
    workflow_name?: string;
    method?: string;
    current_stage?: string;
    stages?: string[];
    status?: string;
  };
  client: {
    name?: string;
    email?: string;
  } | null;
  checks: Array<{ id: string; label?: string; type: string; status: string }>;
};

const COUNTRIES = ["Ethiopia", "Kenya", "Uganda", "United Kingdom", "United States"];

export default function VerifyHostedPage() {
  const params = useParams<{ token: string }>();
  const [data, setData] = useState<SessionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [country, setCountry] = useState("Ethiopia");
  const [mode, setMode] = useState<"device" | "phone" | "sdk">("device");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/verify/${params.token}`, { cache: "no-store" });
      if (!res.ok) throw new Error("Verification session not found");
      setData((await res.json()) as SessionData);
    } finally {
      setLoading(false);
    }
  }, [params.token]);

  useEffect(() => {
    load().catch(console.error);
  }, [load]);

  async function progress(stage: string) {
    setBusy(true);
    try {
      await fetch(`/api/verify/${params.token}/progress`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage, country, mode }),
      });
      await load();
    } finally {
      setBusy(false);
    }
  }

  const currentStage = data?.session.current_stage || "consent";
  const mobileLink = useMemo(() => {
    if (typeof window === "undefined") return "";
    return `${window.location.origin}/verify/${params.token}`;
  }, [params.token]);
  const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=${encodeURIComponent(mobileLink)}`;

  if (loading) {
    return <div className="grid min-h-screen place-items-center bg-white text-black">Loading verification…</div>;
  }

  if (!data) {
    return <div className="grid min-h-screen place-items-center bg-white text-black">Verification not found.</div>;
  }

  return (
    <div className="min-h-screen bg-white px-4 py-10 text-black">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-4xl font-semibold">Verify your identity now</h1>
        <p className="mt-2 text-sm text-neutral-600">
          {data.client?.name || data.session.client_name}, complete the simple steps below.
        </p>

        <div className="mt-8 rounded-2xl border border-neutral-200 p-6">
          <ol className="space-y-4 text-sm">
            {[
              ["consent", "Consent"],
              ["document", "Document Capture"],
              ["face", "Face Capture"],
              ["screening", "Review Checks"],
              ["complete", "Complete"],
            ].map(([id, label], idx) => {
              const active = currentStage === id;
              const done =
                (data.session.stages || []).indexOf(currentStage) > (data.session.stages || []).indexOf(id) ||
                (id === "complete" && data.session.status === "completed");
              return (
                <li key={id} className="flex items-start gap-3">
                  <div
                    className={`mt-0.5 grid h-6 w-6 place-items-center rounded-full text-xs ${
                      active || done ? "bg-blue-600 text-white" : "bg-neutral-200 text-neutral-700"
                    }`}
                  >
                    {idx + 1}
                  </div>
                  <div>
                    <div className="font-medium">{label}</div>
                    <div className="text-neutral-500">
                      {id === "consent" && "Review and accept to proceed."}
                      {id === "document" && "Provide your document using this device, phone, or SDK."}
                      {id === "face" && "Capture a selfie / liveness step."}
                      {id === "screening" && "Finalize workflow checks."}
                      {id === "complete" && "Verification finishes and checks are marked complete."}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>

          <StageCard
            currentStage={currentStage}
            busy={busy}
            country={country}
            setCountry={setCountry}
            mode={mode}
            setMode={setMode}
            mobileLink={mobileLink}
            qrUrl={qrUrl}
            onProgress={progress}
            completed={data.session.status === "completed"}
          />
        </div>

        <div className="mt-6 rounded-2xl border border-neutral-200 p-6">
          <h2 className="text-lg font-semibold">Checks in this verification</h2>
          <div className="mt-3 space-y-2">
            {data.checks.map((check) => (
              <div key={check.id} className="flex items-center justify-between rounded-lg border border-neutral-200 px-3 py-2 text-sm">
                <div>{check.label || check.type.replaceAll("_", " ")}</div>
                <div className={check.status === "complete" ? "text-green-600" : "text-neutral-500"}>{check.status}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function StageCard({
  currentStage,
  busy,
  country,
  setCountry,
  mode,
  setMode,
  mobileLink,
  qrUrl,
  onProgress,
  completed,
}: {
  currentStage: string;
  busy: boolean;
  country: string;
  setCountry: (v: string) => void;
  mode: "device" | "phone" | "sdk";
  setMode: (v: "device" | "phone" | "sdk") => void;
  mobileLink: string;
  qrUrl: string;
  onProgress: (stage: string) => void;
  completed: boolean;
}) {
  if (completed || currentStage === "complete") {
    return (
      <div className="mt-8 rounded-xl bg-green-50 p-6">
        <h3 className="text-xl font-semibold text-green-700">Verification complete</h3>
        <p className="mt-2 text-sm text-green-800">All checks were created and marked complete for this client.</p>
      </div>
    );
  }

  if (currentStage === "consent") {
    return (
      <div className="mt-8">
        <button
          disabled={busy}
          onClick={() => onProgress("consent")}
          className="w-full rounded-lg bg-blue-600 px-4 py-3 text-white disabled:opacity-60"
        >
          {busy ? "Starting…" : "Start"}
        </button>
      </div>
    );
  }

  if (currentStage === "document") {
    return (
      <div className="mt-8 space-y-4">
        <h3 className="text-2xl font-semibold">Document verification</h3>
        <label className="block text-sm">
          <span className="text-neutral-600">Issuing country</span>
          <select
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2"
          >
            {COUNTRIES.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <ModePicker mode={mode} setMode={setMode} />
        {mode === "phone" ? <PhonePanel mobileLink={mobileLink} qrUrl={qrUrl} /> : null}
        {mode === "sdk" ? <SdkPanel token={mobileLink.split("/").pop() || ""} /> : null}
        <button
          disabled={busy}
          onClick={() => onProgress("document")}
          className="w-full rounded-lg bg-blue-600 px-4 py-3 text-white disabled:opacity-60"
        >
          {busy ? "Saving…" : mode === "device" ? "Upload existing photo" : mode === "phone" ? "I uploaded on phone" : "Mark SDK upload complete"}
        </button>
      </div>
    );
  }

  if (currentStage === "face") {
    return (
      <div className="mt-8 space-y-4">
        <h3 className="text-2xl font-semibold">Face capture</h3>
        <p className="text-sm text-neutral-600">Complete the selfie/liveness step using the same method.</p>
        <ModePicker mode={mode} setMode={setMode} />
        {mode === "phone" ? <PhonePanel mobileLink={mobileLink} qrUrl={qrUrl} /> : null}
        {mode === "sdk" ? <SdkPanel token={mobileLink.split("/").pop() || ""} /> : null}
        <button
          disabled={busy}
          onClick={() => onProgress("face")}
          className="w-full rounded-lg bg-blue-600 px-4 py-3 text-white disabled:opacity-60"
        >
          {busy ? "Saving…" : mode === "device" ? "Complete face capture" : mode === "phone" ? "I completed on phone" : "Mark SDK face capture complete"}
        </button>
      </div>
    );
  }

  return (
    <div className="mt-8 space-y-4">
      <h3 className="text-2xl font-semibold">Run workflow checks</h3>
      <p className="text-sm text-neutral-600">Finalize the remaining AML / workflow checks for this verification.</p>
      <button
        disabled={busy}
        onClick={() => onProgress(currentStage === "screening" ? "screening" : "complete")}
        className="w-full rounded-lg bg-blue-600 px-4 py-3 text-white disabled:opacity-60"
      >
        {busy ? "Finishing…" : "Complete verification"}
      </button>
    </div>
  );
}

function ModePicker({
  mode,
  setMode,
}: {
  mode: "device" | "phone" | "sdk";
  setMode: (v: "device" | "phone" | "sdk") => void;
}) {
  return (
    <div className="grid gap-2 md:grid-cols-3">
      {[
        ["device", "Use this device"],
        ["phone", "Continue on phone"],
        ["sdk", "Use SDK token"],
      ].map(([id, label]) => (
        <button
          key={id}
          type="button"
          onClick={() => setMode(id as "device" | "phone" | "sdk")}
          className={`rounded-lg border px-3 py-2 text-sm ${mode === id ? "border-blue-600 bg-blue-50 text-blue-700" : "border-neutral-300"}`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function PhonePanel({ mobileLink, qrUrl }: { mobileLink: string; qrUrl: string }) {
  return (
    <div className="rounded-xl border border-neutral-200 p-4">
      <div className="flex flex-col items-center gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={qrUrl} alt="Continue on phone QR" width={180} height={180} className="rounded-lg" />
        <p className="text-sm text-neutral-600">Scan the QR code or copy the mobile link below.</p>
        <code className="block w-full break-all rounded bg-neutral-100 px-3 py-2 text-xs">{mobileLink}</code>
      </div>
    </div>
  );
}

function SdkPanel({ token }: { token: string }) {
  return (
    <div className="rounded-xl border border-neutral-200 p-4">
      <p className="text-sm text-neutral-600">Use this hosted verification token in your Web/Mobile SDK flow.</p>
      <code className="mt-2 block rounded bg-neutral-100 px-3 py-2 text-xs">{token}</code>
      <pre className="mt-3 overflow-x-auto rounded bg-neutral-100 p-3 text-xs">{`const verificationToken = "${token}";`}</pre>
    </div>
  );
}
