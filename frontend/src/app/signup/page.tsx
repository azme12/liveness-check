"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { FormEvent, useState } from "react";
import { api, setSession } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [organization, setOrganization] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await api<{ access_token: string; user: unknown }>("/api/auth/signup", {
        method: "POST",
        auth: false,
        body: JSON.stringify({
          full_name: fullName,
          email,
          password,
          organization_name: organization || "My Organization",
        }),
      });
      setSession(data.access_token, data.user);
      router.replace("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen grid place-items-center px-4 bg-[radial-gradient(circle_at_top,#064e3b55,transparent_45%),linear-gradient(180deg,#0c0d10,#12151c)]">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-[var(--bg-panel)] p-8 shadow-2xl"
      >
        <div className="mb-6">
          <div className="mb-4 grid h-11 w-11 place-items-center rounded-lg bg-[var(--accent)] text-lg font-bold text-white">
            T
          </div>
          <h1 className="text-2xl font-semibold">Create your Trustanova account</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">Start verifying clients in minutes.</p>
        </div>
        <label className="block text-sm mb-3">
          <span className="text-[var(--muted)]">Full name</span>
          <input
            className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none focus:border-[var(--accent)]"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
          />
        </label>
        <label className="block text-sm mb-3">
          <span className="text-[var(--muted)]">Organization</span>
          <input
            className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none focus:border-[var(--accent)]"
            value={organization}
            onChange={(e) => setOrganization(e.target.value)}
            placeholder="StarPay Ethiopia Finance"
          />
        </label>
        <label className="block text-sm mb-3">
          <span className="text-[var(--muted)]">Email</span>
          <input
            className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 outline-none focus:border-[var(--accent)]"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            required
          />
        </label>
        <label className="block text-sm mb-4">
          <span className="text-[var(--muted)]">Password</span>
          <div className="relative mt-1">
            <input
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2 pr-10 outline-none focus:border-[var(--accent)]"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              minLength={6}
              required
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-[var(--muted)] hover:text-white"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>
        </label>
        {error ? <p className="mb-3 text-sm text-[var(--danger)]">{error}</p> : null}
        <button
          disabled={loading}
          className="w-full rounded-lg bg-[var(--accent)] py-2.5 font-semibold text-white hover:brightness-110 disabled:opacity-60"
        >
          {loading ? "Creating…" : "Sign up"}
        </button>
        <p className="mt-4 text-center text-sm text-[var(--muted)]">
          Already have an account?{" "}
          <Link href="/login" className="text-[var(--accent)] hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </div>
  );
}
