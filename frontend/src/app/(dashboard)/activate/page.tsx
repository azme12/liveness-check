"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Panel } from "@/components/AppShell";
import { api } from "@/lib/api";
import { useEnvironment } from "@/lib/environment";
import { cn } from "@/lib/format";

const STEPS = [
  { id: 1, label: "Business details" },
  { id: 2, label: "Business address" },
  { id: 3, label: "About usage" },
  { id: 4, label: "Identity verification" },
];

const COUNTRIES = ["Ethiopia", "Kenya", "United Kingdom", "United States", "United Arab Emirates", "Germany"];
const INDUSTRIES = [
  "Financial services",
  "Fintech",
  "Marketplace",
  "Crypto / digital assets",
  "Healthcare",
  "Other",
];

type ActivationState = {
  step?: number;
  completed?: boolean;
  business_details?: Record<string, string>;
  business_address?: Record<string, string>;
  usage?: Record<string, string>;
  identity?: Record<string, string | boolean>;
};

export default function ActivatePage() {
  const router = useRouter();
  const { setLiveEnabled, setEnv } = useEnvironment();
  const [step, setStep] = useState(1);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const [legalName, setLegalName] = useState("");
  const [regNumber, setRegNumber] = useState("");
  const [taxNumber, setTaxNumber] = useState("");
  const [country, setCountry] = useState("");
  const [industry, setIndustry] = useState("");

  const [line1, setLine1] = useState("");
  const [line2, setLine2] = useState("");
  const [city, setCity] = useState("");
  const [region, setRegion] = useState("");
  const [postal, setPostal] = useState("");
  const [addrCountry, setAddrCountry] = useState("");

  const [volume, setVolume] = useState("");
  const [useCase, setUseCase] = useState("");
  const [regions, setRegions] = useState("");

  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("");
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    api<{ live_enabled: boolean; activation: ActivationState }>("/api/auth/activation")
      .then((data) => {
        if (data.live_enabled || data.activation?.completed) {
          setLiveEnabled(true);
          router.replace("/home");
          return;
        }
        const a = data.activation || {};
        setStep(Math.min(4, Math.max(1, a.step || 1)));
        if (a.business_details) {
          setLegalName(a.business_details.legal_company_name || "");
          setRegNumber(a.business_details.registration_number || "");
          setTaxNumber(a.business_details.tax_number || "");
          setCountry(a.business_details.incorporation_country || "");
          setIndustry(a.business_details.industry || "");
        }
        if (a.business_address) {
          setLine1(a.business_address.line1 || "");
          setLine2(a.business_address.line2 || "");
          setCity(a.business_address.city || "");
          setRegion(a.business_address.region || "");
          setPostal(a.business_address.postal_code || "");
          setAddrCountry(a.business_address.country || "");
        }
        if (a.usage) {
          setVolume(a.usage.monthly_volume || "");
          setUseCase(a.usage.primary_use_case || "");
          setRegions(a.usage.regions || "");
        }
        if (a.identity) {
          setFullName(String(a.identity.full_name || ""));
          setRole(String(a.identity.role || ""));
        }
      })
      .catch(console.error);
  }, [router, setLiveEnabled]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSaving(true);
    try {
      if (step === 1) {
        await api("/api/auth/activation/business-details", {
          method: "POST",
          body: JSON.stringify({
            legal_company_name: legalName,
            registration_number: regNumber,
            tax_number: taxNumber || null,
            incorporation_country: country,
            industry,
          }),
        });
        setStep(2);
      } else if (step === 2) {
        await api("/api/auth/activation/business-address", {
          method: "POST",
          body: JSON.stringify({
            line1,
            line2: line2 || null,
            city,
            region: region || null,
            postal_code: postal,
            country: addrCountry,
          }),
        });
        setStep(3);
      } else if (step === 3) {
        await api("/api/auth/activation/usage", {
          method: "POST",
          body: JSON.stringify({
            monthly_volume: volume,
            primary_use_case: useCase,
            regions,
          }),
        });
        setStep(4);
      } else {
        const res = await api<{ live_enabled: boolean }>("/api/auth/activation/identity", {
          method: "POST",
          body: JSON.stringify({ full_name: fullName, role, confirmed }),
        });
        setLiveEnabled(Boolean(res.live_enabled));
        setEnv("live");
        router.replace("/home");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="mb-6 text-2xl font-semibold">Activate your account</h1>
      <div className="mb-6 flex flex-wrap gap-2">
        {STEPS.map((s) => (
          <div
            key={s.id}
            className={cn(
              "rounded-md border px-3 py-1.5 text-sm",
              step === s.id
                ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent)]"
                : step > s.id
                  ? "border-[var(--border)] text-[var(--text)]"
                  : "border-[var(--border)] text-[var(--muted)]",
            )}
          >
            {s.id}. {s.label}
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_0.8fr]">
        <Panel className="p-5">
          <form onSubmit={submit} className="space-y-4">
            {step === 1 ? (
              <>
                <h2 className="text-lg font-semibold">Business details</h2>
                <Field label="Legal company name *" value={legalName} onChange={setLegalName} placeholder="e.g. Global Bank Limited" required />
                <Field label="Registration number *" value={regNumber} onChange={setRegNumber} placeholder="e.g. A123-2010N" required />
                <Field label="Tax number" value={taxNumber} onChange={setTaxNumber} placeholder="Company VAT or Tax number" />
                <Select label="Incorporation country *" value={country} onChange={setCountry} options={COUNTRIES} required />
                <Select label="Industry *" value={industry} onChange={setIndustry} options={INDUSTRIES} required />
              </>
            ) : null}

            {step === 2 ? (
              <>
                <h2 className="text-lg font-semibold">Business address</h2>
                <Field label="Address line 1 *" value={line1} onChange={setLine1} required />
                <Field label="Address line 2" value={line2} onChange={setLine2} />
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="City *" value={city} onChange={setCity} required />
                  <Field label="Region / State" value={region} onChange={setRegion} />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <Field label="Postal code *" value={postal} onChange={setPostal} required />
                  <Select label="Country *" value={addrCountry} onChange={setAddrCountry} options={COUNTRIES} required />
                </div>
              </>
            ) : null}

            {step === 3 ? (
              <>
                <h2 className="text-lg font-semibold">About usage</h2>
                <Select
                  label="Expected monthly volume *"
                  value={volume}
                  onChange={setVolume}
                  options={["Under 1,000", "1,000 – 10,000", "10,000 – 100,000", "100,000+"]}
                  required
                />
                <Field
                  label="Primary use case *"
                  value={useCase}
                  onChange={setUseCase}
                  placeholder="e.g. Onboarding KYC for mobile banking"
                  required
                />
                <Field
                  label="Regions served"
                  value={regions}
                  onChange={setRegions}
                  placeholder="e.g. East Africa, EU"
                />
              </>
            ) : null}

            {step === 4 ? (
              <>
                <h2 className="text-lg font-semibold">Identity verification</h2>
                <p className="text-sm text-[var(--muted)]">
                  Confirm the authorised representative for this business to unlock LIVE.
                </p>
                <Field label="Full name *" value={fullName} onChange={setFullName} required />
                <Field label="Role *" value={role} onChange={setRole} placeholder="e.g. Director / Compliance officer" required />
                <label className="flex items-start gap-2 text-sm text-[var(--muted)]">
                  <input
                    type="checkbox"
                    checked={confirmed}
                    onChange={(e) => setConfirmed(e.target.checked)}
                    className="mt-1"
                    required
                  />
                  I confirm I am authorised to activate LIVE for this organisation.
                </label>
              </>
            ) : null}

            {error ? <p className="text-sm text-[var(--danger)]">{error}</p> : null}
            <div className="flex justify-end gap-2 pt-2">
              {step > 1 ? (
                <button
                  type="button"
                  onClick={() => setStep((s) => s - 1)}
                  className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm"
                >
                  Back
                </button>
              ) : null}
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-[var(--success)] px-4 py-2 text-sm font-semibold text-black disabled:opacity-60"
              >
                {saving ? "Saving…" : step === 4 ? "Activate LIVE" : "Save and proceed →"}
              </button>
            </div>
          </form>
        </Panel>

        <Panel className="h-fit p-5">
          <h3 className="font-semibold">Tell us about your business</h3>
          <p className="mt-2 text-sm text-[var(--muted)]">
            Trustanova provides identity verification and KYC/AML compliance services. To grant access
            to LIVE data, we need basic business details to meet regulatory obligations.
          </p>
          <p className="mt-3 text-sm text-[var(--muted)]">
            Until activation is complete you can only use <strong className="text-[var(--text)]">TEST</strong>{" "}
            mode — no real verifications are processed.
          </p>
        </Panel>
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
        {label}
      </span>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none focus:border-[var(--accent)]"
      />
    </label>
  );
}

function Select({
  label,
  value,
  onChange,
  options,
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
  required?: boolean;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none focus:border-[var(--accent)]"
      >
        <option value="">Select…</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
}
