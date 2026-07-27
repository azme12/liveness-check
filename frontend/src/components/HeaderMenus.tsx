"use client";

import Link from "next/link";
import { CircleHelp, ExternalLink, Moon, Sun, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTheme, type ThemeMode } from "@/lib/theme";
import { cn } from "@/lib/format";

export function ThemeMenu() {
  const { theme, resolved, setTheme } = useTheme();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const options: { id: ThemeMode; label: string }[] = [
    { id: "light", label: "Light Mode" },
    { id: "dark", label: "Dark Mode" },
    { id: "system", label: "System" },
  ];

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        title="Appearance"
        onClick={() => setOpen((v) => !v)}
        className="hidden sm:grid h-8 w-8 place-items-center rounded-md text-[var(--muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)]"
      >
        {resolved === "light" ? <Sun size={16} /> : <Moon size={16} />}
      </button>
      {open ? (
        <div className="absolute right-0 top-10 z-50 w-[320px] rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)] p-3 shadow-[var(--popover-shadow)]">
          <p className="mb-3 px-1 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
            Appearance
          </p>
          <div className="grid grid-cols-3 gap-2">
            {options.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => {
                  setTheme(opt.id);
                  setOpen(false);
                }}
                className={cn(
                  "rounded-lg border p-2 text-left transition",
                  theme === opt.id
                    ? "border-[var(--accent)] ring-1 ring-[var(--accent)]"
                    : "border-[var(--border)] hover:border-[var(--muted)]",
                )}
              >
                <ThemePreview mode={opt.id} />
                <p className="mt-2 text-center text-[11px] font-medium">{opt.label}</p>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ThemePreview({ mode }: { mode: ThemeMode }) {
  if (mode === "system") {
    return (
      <div className="flex h-16 overflow-hidden rounded-md border border-[var(--border)]">
        <div className="w-1/2 bg-[#f4f6f9] p-1.5">
          <div className="h-2 w-8 rounded bg-[#d8dee8]" />
          <div className="mt-1.5 h-8 rounded bg-white border border-[#e5e9f0]" />
        </div>
        <div className="w-1/2 bg-[#0c0d10] p-1.5">
          <div className="h-2 w-8 rounded bg-[#2a2f3a]" />
          <div className="mt-1.5 h-8 rounded bg-[#1a1d24] border border-[#2a2f3a]" />
        </div>
      </div>
    );
  }
  const light = mode === "light";
  return (
    <div
      className={cn(
        "h-16 rounded-md border p-1.5",
        light ? "border-[#d8dee8] bg-[#f4f6f9]" : "border-[#2a2f3a] bg-[#0c0d10]",
      )}
    >
      <div className={cn("h-2 w-10 rounded", light ? "bg-[#d8dee8]" : "bg-[#2a2f3a]")} />
      <div
        className={cn(
          "mt-1.5 h-8 rounded border",
          light ? "border-[#e5e9f0] bg-white" : "border-[#2a2f3a] bg-[#1a1d24]",
        )}
      />
    </div>
  );
}

export function HelpMenu() {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const links = [
    { label: "API documentation", href: "/integration/api-docs" },
    { label: "Webhooks guide", href: "/integration/webhooks" },
    { label: "Workflows", href: "/workflows" },
  ];

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        title="Help"
        onClick={() => setOpen((v) => !v)}
        className="hidden sm:grid h-8 w-8 place-items-center rounded-md text-[var(--muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)]"
      >
        <CircleHelp size={16} />
      </button>
      {open ? (
        <div className="absolute right-0 top-10 z-50 w-72 rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)] shadow-[var(--popover-shadow)]">
          <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
            <h2 className="text-sm font-semibold">Help</h2>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="grid h-7 w-7 place-items-center rounded-md text-[var(--muted)] hover:bg-[var(--bg-hover)]"
            >
              <X size={14} />
            </button>
          </div>
          <div className="p-2">
            {links.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                onClick={() => setOpen(false)}
                className="flex items-center justify-between rounded-md px-3 py-2 text-sm text-[var(--muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)]"
              >
                {link.label}
                <ExternalLink size={12} />
              </Link>
            ))}
            <a
              href="mailto:support@trustanova.dev"
              className="mt-1 flex items-center justify-between rounded-md px-3 py-2 text-sm text-[var(--muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)]"
            >
              Contact support
              <ExternalLink size={12} />
            </a>
          </div>
        </div>
      ) : null}
    </div>
  );
}
