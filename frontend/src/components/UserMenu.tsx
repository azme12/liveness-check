"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut, UserRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { clearSession } from "@/lib/api";

type UserMenuProps = {
  name: string;
  email: string;
};

export function UserMenu({ name, email }: UserMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        title="Account"
        onClick={() => setOpen((v) => !v)}
        className="grid h-8 w-8 place-items-center rounded-full bg-[var(--bg-hover)] text-[var(--muted)] hover:text-[var(--text)]"
      >
        <UserRound size={16} />
      </button>
      {open ? (
        <div className="absolute right-0 top-10 z-50 w-64 overflow-hidden rounded-xl border border-[var(--border)] bg-[var(--bg-elevated)] shadow-[var(--popover-shadow)]">
          <div className="border-b border-[var(--border)] px-4 py-3">
            <p className="truncate text-sm font-semibold">{name || "User"}</p>
            <p className="truncate text-xs text-[var(--muted)]">{email}</p>
          </div>
          <div className="p-2">
            <p className="px-2 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-wide text-[var(--muted)]">
              Preferences
            </p>
            <Link
              href="/settings/account"
              onClick={() => setOpen(false)}
              className="block rounded-md px-2.5 py-2 text-sm text-[var(--muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)]"
            >
              Profile
            </Link>
            <Link
              href="/settings/notifications"
              onClick={() => setOpen(false)}
              className="block rounded-md px-2.5 py-2 text-sm text-[var(--muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)]"
            >
              Language
              <span className="ml-2 text-xs opacity-70">EN</span>
            </Link>
            <button
              type="button"
              onClick={() => {
                clearSession();
                router.replace("/login");
              }}
              className="mt-1 flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm text-[var(--danger)] hover:bg-[var(--bg-hover)]"
            >
              <LogOut size={14} />
              Sign out
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
