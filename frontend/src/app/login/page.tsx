"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Eye, EyeOff } from "lucide-react";
import { FormEvent, useState } from "react";
import { api, setSession } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("admin@trustanova.dev");
  const [password, setPassword] = useState("admin123");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const data = await api<{ access_token: string; user: unknown }>("/api/auth/login", {
        method: "POST",
        auth: false,
        body: JSON.stringify({ email, password }),
      });
      setSession(data.access_token, data.user);
      router.replace("/home");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
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
          <h1 className="text-2xl font-semibold">Sign in to Trustanova</h1>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Identity verification dashboard — Trustanova workflows.
          </p>
        </div>
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
              autoComplete="current-password"
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
          {loading ? "Signing in…" : "Sign in"}
        </button>
        <p className="mt-4 text-center text-sm text-[var(--muted)]">
          No account?{" "}
          <Link href="/signup" className="text-[var(--accent)] hover:underline">
            Sign up
          </Link>
        </p>
        <p className="mt-3 text-center text-xs text-[var(--muted)]">
          Demo: admin@trustanova.dev / admin123
        </p>
      </form>
    </div>
  );
}
