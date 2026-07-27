"use client";

import Link from "next/link";
import { HelpCircle } from "lucide-react";
import { useEnvironment } from "@/lib/environment";

export function TestModeBanner() {
  const { env, liveEnabled } = useEnvironment();
  if (env !== "test") return null;

  return (
    <div className="flex items-center justify-center gap-2 bg-[#f97316] px-4 py-2 text-center text-sm font-medium text-black">
      <span>You&apos;re using test mode. No real verifications will be processed.</span>
      <HelpCircle size={14} className="opacity-80" />
      {!liveEnabled ? (
        <Link href="/activate" className="ml-2 underline underline-offset-2 hover:no-underline">
          Activate account
        </Link>
      ) : null}
    </div>
  );
}
