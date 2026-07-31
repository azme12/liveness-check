"use client";

import { useParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { verifyUrl } from "@/lib/verifyApi";

type MediaAsset = {
  id: string;
  url: string;
  document_type?: string | null;
  issuing_country?: string | null;
  status?: string;
};

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
    document_id?: string | null;
    live_photo_id?: string | null;
  };
  client: {
    name?: string;
    email?: string;
  } | null;
  document?: MediaAsset | null;
  live_photo?: MediaAsset | null;
  verification_response?: {
    status?: string;
    outcome?: string;
    facial_score?: number;
    liveness_score?: number;
    facialSimilarityScore?: number;
    livenessCheckScore?: number;
    full_name?: string;
    picture?: string | null;
    selfie_photo?: string | null;
    complycube?: {
      identity_outcome?: string;
      identity_status?: string;
      identity_check?: {
        result?: {
          breakdown?: {
            faceAnalysis?: { breakdown?: { facialSimilarityScore?: number } };
            authenticityAnalysis?: { breakdown?: { livenessCheckScore?: number } };
          };
        };
      };
    };
  } | null;
  checks: Array<{
    id: string;
    label?: string;
    type: string;
    status: string;
    outcome?: string | null;
    result?: {
      signals?: {
        scores?: {
          facialSimilarityScore?: number | null;
          livenessCheckScore?: number | null;
          face_match_score?: number | null;
          liveness_score?: number | null;
          document_type?: string | null;
        };
      };
      biometric?: { liveness?: string; liveness_score?: number; face_match_score?: number | null };
      document?: { quality_score?: number; document_type?: string | null };
    } | null;
  }>;
};

const COUNTRIES = ["Ethiopia", "Kenya", "Uganda", "United Kingdom", "United States"];

function VerifyHostedInner() {
  const params = useParams<{ token: string }>();
  const [data, setData] = useState<SessionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [country, setCountry] = useState("Ethiopia");
  const [documentType, setDocumentType] = useState("fayda");
  const [mode, setMode] = useState<"device" | "phone">("device");
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [livePhotoFile, setLivePhotoFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(verifyUrl(`/api/verify/${params.token}`), { cache: "no-store" });
      if (!res.ok) throw new Error("Verification session not found");
      const json = (await res.json()) as SessionData;
      setData(json);
      if (json.document?.document_type) setDocumentType(json.document.document_type);
      if (json.document?.issuing_country) setCountry(json.document.issuing_country);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load verification");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [params.token]);

  useEffect(() => {
    load().catch(console.error);
  }, [load]);

  async function progress(stage: string) {
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const res = await fetch(verifyUrl(`/api/verify/${params.token}/progress`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage, country, mode }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || "Unable to continue verification");
      }
      await load();
      setMessage("Stage updated successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to continue verification");
    } finally {
      setBusy(false);
    }
  }

  async function upload(kind: "document" | "live-photo") {
    const file = kind === "document" ? documentFile : livePhotoFile;
    if (!file) return;
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      if (kind === "document") {
        form.append("document_type", documentType);
        form.append("issuing_country", country);
      }
      const res = await fetch(verifyUrl(`/api/verify/${params.token}/${kind}`), {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || `Unable to upload ${kind}`);
      }
      await load();
      setMessage(
        kind === "document"
          ? "Document uploaded."
          : "Live photo uploaded — face match and liveness scores are being calculated.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : `Unable to upload ${kind}`);
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
    return <div className="grid min-h-[480px] place-items-center bg-white text-black">Loading verification…</div>;
  }

  if (!data) {
    return (
      <div className="grid min-h-[480px] place-items-center bg-white px-4 text-center text-black">
        <div>
          <div className="text-lg font-semibold">Verification not found</div>
          <p className="mt-2 text-sm text-neutral-600">{error || "Check the link and try again."}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white px-4 py-10 text-black">
      <div className="mx-auto max-w-3xl">
        <h1 className="text-3xl font-semibold md:text-4xl">Verify your identity now</h1>
        <p className="mt-2 text-sm text-neutral-600">
          {data.client?.name || data.session.client_name}, complete the simple steps below.
        </p>
        {error ? <div className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div> : null}

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
                      {id === "document" && "Upload your ID or passport photo."}
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
            session={data.session}
            document={data.document}
            livePhoto={data.live_photo}
            currentStage={currentStage}
            busy={busy}
            country={country}
            setCountry={setCountry}
            documentType={documentType}
            setDocumentType={setDocumentType}
            mode={mode}
            setMode={setMode}
            documentFile={documentFile}
            setDocumentFile={setDocumentFile}
            livePhotoFile={livePhotoFile}
            setLivePhotoFile={setLivePhotoFile}
            mobileLink={mobileLink}
            qrUrl={qrUrl}
            onProgress={progress}
            onUpload={upload}
            completed={data.session.status === "completed"}
          />
          {message ? <div className="mt-4 text-sm text-blue-700">{message}</div> : null}
        </div>

        <div className="mt-6 rounded-2xl border border-neutral-200 p-6">
          <h2 className="text-lg font-semibold">Checks in this verification</h2>
          <div className="mt-3 space-y-2">
            {data.checks.map((check) => {
              const scores = check.result?.signals?.scores;
              const facePct =
                typeof scores?.facialSimilarityScore === "number"
                  ? scores.facialSimilarityScore
                  : typeof scores?.face_match_score === "number"
                    ? Math.round(scores.face_match_score * 100)
                    : typeof check.result?.biometric?.face_match_score === "number"
                      ? Math.round(check.result.biometric.face_match_score * 100)
                      : null;
              const livePct =
                typeof scores?.livenessCheckScore === "number"
                  ? scores.livenessCheckScore
                  : typeof scores?.liveness_score === "number"
                    ? Math.round(scores.liveness_score * 100)
                    : typeof check.result?.biometric?.liveness_score === "number"
                      ? Math.round(check.result.biometric.liveness_score * 100)
                      : null;
              return (
              <div key={check.id} className="rounded-lg border border-neutral-200 px-3 py-3 text-sm">
                <div className="flex items-center justify-between gap-3">
                  <div>{check.label || check.type.replaceAll("_", " ")}</div>
                  <div className="text-right">
                    <div className={check.status === "complete" ? "text-green-600" : "text-neutral-500"}>{check.status}</div>
                    <div className="text-xs capitalize text-neutral-500">{check.outcome || "pending"}</div>
                  </div>
                </div>
                {check.result?.document || check.result?.biometric || scores ? (
                  <div className="mt-2 grid gap-2 text-xs text-neutral-600 md:grid-cols-4">
                    <div>
                      <span className="font-medium">Doc type:</span>{" "}
                      {scores?.document_type || check.result?.document?.document_type || "—"}
                    </div>
                    <div>
                      <span className="font-medium">Doc quality:</span>{" "}
                      {typeof check.result?.document?.quality_score === "number"
                        ? Math.round(check.result.document.quality_score * 100)
                        : "—"}
                    </div>
                    <div>
                      <span className="font-medium">Liveness:</span>{" "}
                      {livePct !== null ? `${livePct}` : check.result?.biometric?.liveness || "—"}
                    </div>
                    <div>
                      <span className="font-medium">Face match:</span>{" "}
                      {facePct !== null ? `${facePct}` : "—"}
                    </div>
                  </div>
                ) : null}
              </div>
            );})}
          </div>
        </div>

        {data.verification_response ? (
          <div className="mt-6 rounded-2xl border border-green-200 bg-green-50 p-6 text-sm text-green-950">
            <h2 className="text-lg font-semibold text-green-800">Verification result</h2>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              <div>
                <span className="font-medium">Status:</span> {data.verification_response.status || "—"}
              </div>
              <div>
                <span className="font-medium">Outcome:</span> {data.verification_response.outcome || "—"}
              </div>
              <div>
                <span className="font-medium">Facial similarity:</span>{" "}
                {data.verification_response.facialSimilarityScore ??
                  data.verification_response.facial_score ??
                  "—"}
              </div>
              <div>
                <span className="font-medium">Liveness:</span>{" "}
                {data.verification_response.livenessCheckScore ??
                  data.verification_response.liveness_score ??
                  "—"}
              </div>
            </div>
            <details className="mt-4">
              <summary className="cursor-pointer font-medium text-green-800">Full partner JSON</summary>
              <pre className="mt-2 max-h-64 overflow-auto rounded bg-white p-3 text-xs text-neutral-800">
                {JSON.stringify(data.verification_response, null, 2)}
              </pre>
            </details>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function VerifyHostedPage() {
  return (
    <Suspense fallback={<div className="grid min-h-[480px] place-items-center bg-white text-black">Loading verification…</div>}>
      <VerifyHostedInner />
    </Suspense>
  );
}

function StageCard({
  session,
  document,
  livePhoto,
  currentStage,
  busy,
  country,
  setCountry,
  documentType,
  setDocumentType,
  mode,
  setMode,
  documentFile,
  setDocumentFile,
  livePhotoFile,
  setLivePhotoFile,
  mobileLink,
  qrUrl,
  onProgress,
  onUpload,
  completed,
}: {
  session: SessionData["session"];
  document?: MediaAsset | null;
  livePhoto?: MediaAsset | null;
  currentStage: string;
  busy: boolean;
  country: string;
  setCountry: (v: string) => void;
  documentType: string;
  setDocumentType: (v: string) => void;
  mode: "device" | "phone";
  setMode: (v: "device" | "phone") => void;
  documentFile: File | null;
  setDocumentFile: (v: File | null) => void;
  livePhotoFile: File | null;
  setLivePhotoFile: (v: File | null) => void;
  mobileLink: string;
  qrUrl: string;
  onProgress: (stage: string) => void;
  onUpload: (kind: "document" | "live-photo") => void;
  completed: boolean;
}) {
  if (completed || currentStage === "complete") {
    return (
      <div className="mt-8 rounded-xl bg-green-50 p-6">
        <h3 className="text-xl font-semibold text-green-700">Verification complete</h3>
        <p className="mt-2 text-sm text-green-800">Checks finished and results were stored for this client.</p>
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
    const documentUrl = document?.url ? verifyUrl(document.url) : null;
    return (
      <div className="mt-8 space-y-4">
        <h3 className="text-2xl font-semibold">Document verification</h3>
        {documentUrl ? (
          <div className="rounded-xl border border-green-200 bg-green-50 p-4 text-sm text-green-900">
            <div className="font-medium">Document already uploaded</div>
            <p className="mt-1 text-green-800">
              Using your uploaded {document?.document_type?.replaceAll("_", " ") || "ID"} photo — no need to upload again.
            </p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={documentUrl}
              alt="Uploaded document"
              className="mt-3 max-h-56 w-full rounded-lg border border-green-200 object-contain bg-white"
            />
          </div>
        ) : (
          <>
            <label className="block text-sm">
              <span className="text-neutral-600">Document type</span>
              <select
                value={documentType}
                onChange={(e) => setDocumentType(e.target.value)}
                className="mt-1 w-full rounded-lg border border-neutral-300 px-3 py-2"
              >
                <option value="fayda">Fayda ID (Ethiopia digital ID)</option>
                <option value="kebele_id">Kebele ID</option>
                <option value="national_id">National ID card</option>
                <option value="passport">Passport</option>
                <option value="driving_license">Driving license</option>
              </select>
            </label>
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
            <label className="block rounded-lg border border-dashed border-neutral-300 p-4 text-sm">
              <span className="text-neutral-600">Upload document image</span>
              <input className="mt-2 block w-full" type="file" accept="image/*" onChange={(e) => setDocumentFile(e.target.files?.[0] || null)} />
            </label>
          </>
        )}
        <div className="flex gap-3">
          {!documentUrl ? (
            <button
              disabled={busy || !documentFile}
              onClick={() => onUpload("document")}
              className="flex-1 rounded-lg border border-neutral-300 px-4 py-3 disabled:opacity-60"
            >
              {busy ? "Uploading…" : "Upload document"}
            </button>
          ) : null}
          <button
            disabled={busy || !session.document_id}
            onClick={() => onProgress("document")}
            className="flex-1 rounded-lg bg-blue-600 px-4 py-3 text-white disabled:opacity-60"
          >
            {documentUrl ? "Continue with uploaded document" : "Continue"}
          </button>
        </div>
      </div>
    );
  }

  if (currentStage === "face") {
    const livePhotoUrl = livePhoto?.url ? verifyUrl(livePhoto.url) : null;
    return (
      <div className="mt-8 space-y-4">
        <h3 className="text-2xl font-semibold">Face capture</h3>
        {document?.url ? (
          <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-3 text-xs text-neutral-600">
            Document on file:{" "}
            <a href={verifyUrl(document.url)} target="_blank" rel="noreferrer" className="text-blue-600 underline">
              view uploaded ID
            </a>
          </div>
        ) : null}
        <p className="text-sm text-neutral-600">
          {livePhotoUrl
            ? "Your selfie is already uploaded. Run the liveness + face match check below."
            : `Upload a selfie — we match it to your ${documentType.replaceAll("_", " ")} photo and run liveness automatically.`}
        </p>
        {livePhotoUrl ? (
          <div className="rounded-xl border border-green-200 bg-green-50 p-4 text-sm text-green-900">
            <div className="font-medium">Selfie already uploaded</div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={livePhotoUrl}
              alt="Uploaded selfie"
              className="mt-3 max-h-56 w-full rounded-lg border border-green-200 object-contain bg-white"
            />
          </div>
        ) : (
          <>
            <ModePicker mode={mode} setMode={setMode} />
            {mode === "phone" ? <PhonePanel mobileLink={mobileLink} qrUrl={qrUrl} /> : null}
            <label className="block rounded-lg border border-dashed border-neutral-300 p-4 text-sm">
              <span className="text-neutral-600">Upload selfie / live photo</span>
              <input className="mt-2 block w-full" type="file" accept="image/*" onChange={(e) => setLivePhotoFile(e.target.files?.[0] || null)} />
            </label>
          </>
        )}
        <div className="flex gap-3">
          {!livePhotoUrl ? (
            <button
              disabled={busy || !livePhotoFile}
              onClick={() => onUpload("live-photo")}
              className="flex-1 rounded-lg border border-neutral-300 px-4 py-3 disabled:opacity-60"
            >
              {busy ? "Uploading…" : "Upload selfie"}
            </button>
          ) : null}
          <button
            disabled={busy || !session.live_photo_id}
            onClick={() => onProgress("face")}
            className="flex-1 rounded-lg bg-blue-600 px-4 py-3 text-white disabled:opacity-60"
          >
            {livePhotoUrl ? "Run check on uploaded selfie" : "Run liveness check"}
          </button>
        </div>
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
  mode: "device" | "phone";
  setMode: (v: "device" | "phone") => void;
}) {
  return (
    <div className="grid gap-2 md:grid-cols-2">
      {[
        ["device", "Use this device"],
        ["phone", "Continue on phone"],
      ].map(([id, label]) => (
        <button
          key={id}
          type="button"
          onClick={() => setMode(id as "device" | "phone")}
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
