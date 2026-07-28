"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BookOpen,
  ChevronDown,
  Globe,
  KeyRound,
  LayoutGrid,
  List,
  Logs,
  Search,
  Settings,
  Shield,
  Smartphone,
  Webhook,
} from "lucide-react";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { HelpMenu, ThemeMenu } from "@/components/HeaderMenus";
import { NotificationsMenu } from "@/components/NotificationsMenu";
import { TestModeBanner } from "@/components/TestModeBanner";
import { UserMenu } from "@/components/UserMenu";
import { api, getStoredUser } from "@/lib/api";
import { useEnvironment } from "@/lib/environment";
import { cn } from "@/lib/format";
import { useTheme } from "@/lib/theme";

const NAV = [
  { href: "/home", label: "Home" },
  { href: "/clients", label: "Clients" },
  { href: "/sessions", label: "Sessions" },
  { href: "/checks", label: "Checks" },
  { href: "/workflows", label: "Workflows" },
  { href: "/integration", label: "Integration" },
];

const INTEGRATION_NAV = [
  { href: "/integration", label: "Integration", icon: LayoutGrid },
  { href: "/integration/api-keys", label: "API keys", icon: KeyRound },
  { href: "/integration/web", label: "Web SDK", icon: Globe },
  { href: "/integration/allowed-ips", label: "Allowed IPs", icon: Shield },
  { href: "/integration/webhooks", label: "Webhooks", icon: Webhook },
  { href: "/integration/events", label: "Events", icon: List },
  { href: "/integration/logs", label: "Logs", icon: Logs },
  { href: "/integration/mobile", label: "Mobile App", icon: Smartphone },
  { href: "/integration/api-docs", label: "API Docs", icon: BookOpen },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { hydrateTheme } = useTheme();
  const { env, setEnv, liveEnabled, setLiveEnabled } = useEnvironment();
  const [orgName, setOrgName] = useState("Trustanova Org");
  const [userName, setUserName] = useState("User");
  const [userEmail, setUserEmail] = useState("");
  const [liveTip, setLiveTip] = useState(false);
  const showIntegrationSidebar = pathname.startsWith("/integration");

  useEffect(() => {
    const user = getStoredUser<{ full_name?: string; email?: string; org_id?: string; theme?: string }>();
    const token = localStorage.getItem("trustanova_token");
    if (!token || !user) {
      router.replace("/login");
      return;
    }
    setUserName(user.full_name || "User");
    setUserEmail(user.email || "");

    const cacheKey = "trustanova_me_cache";
    const cachedRaw = sessionStorage.getItem(cacheKey);
    if (cachedRaw) {
      try {
        const cached = JSON.parse(cachedRaw) as {
          at: number;
          data: {
            organization?: { name?: string; live_enabled?: boolean };
            live_enabled?: boolean;
            user?: { full_name?: string; email?: string; first_name?: string; theme?: string };
          };
        };
        if (Date.now() - cached.at < 60_000) {
          const data = cached.data;
          if (data.organization?.name) setOrgName(data.organization.name);
          if (data.user?.full_name) setUserName(data.user.full_name);
          else if (data.user?.first_name) setUserName(data.user.first_name);
          if (data.user?.email) setUserEmail(data.user.email);
          const enabled = Boolean(data.live_enabled ?? data.organization?.live_enabled);
          setLiveEnabled(enabled);
          if (!enabled) setEnv("test");
          if (data.user?.theme && ["light", "dark", "system"].includes(data.user.theme)) {
            hydrateTheme(data.user.theme as "light" | "dark" | "system");
          }
          return;
        }
      } catch {
        /* ignore bad cache */
      }
    }

    api<{
      organization?: { name?: string; live_enabled?: boolean };
      live_enabled?: boolean;
      user?: { full_name?: string; email?: string; first_name?: string; theme?: string };
    }>("/api/auth/me")
      .then((data) => {
        sessionStorage.setItem(cacheKey, JSON.stringify({ at: Date.now(), data }));
        if (data.organization?.name) setOrgName(data.organization.name);
        if (data.user?.full_name) setUserName(data.user.full_name);
        else if (data.user?.first_name) setUserName(data.user.first_name);
        if (data.user?.email) setUserEmail(data.user.email);
        const enabled = Boolean(data.live_enabled ?? data.organization?.live_enabled);
        setLiveEnabled(enabled);
        if (!enabled) setEnv("test");
        if (data.user?.theme && ["light", "dark", "system"].includes(data.user.theme)) {
          hydrateTheme(data.user.theme as "light" | "dark" | "system");
        }
      })
      .catch(() => undefined);
  }, [router, hydrateTheme, setLiveEnabled, setEnv]);

  const activeNav = useMemo(() => {
    return NAV.find((n) => pathname === n.href || pathname.startsWith(`${n.href}/`))?.href;
  }, [pathname]);

  return (
    <div className="min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <TestModeBanner />
      <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--bg-elevated)]/95 backdrop-blur">
        <div className="flex h-14 items-center gap-3 px-4">
          <Link href="/home" className="flex items-center gap-2 shrink-0">
            <span className="grid h-8 w-8 place-items-center rounded-md bg-[var(--accent)] text-white font-bold">
              T
            </span>
          </Link>
          <div className="hidden md:flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-sm text-[var(--muted)] w-56">
            <Search size={14} />
            <span>Search...</span>
            <span className="ml-auto text-xs opacity-70">Ctrl K</span>
          </div>
          <nav className="hidden lg:flex items-center gap-1 ml-2">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm transition",
                  activeNav === item.href
                    ? "bg-[var(--accent)] text-white"
                    : "text-[var(--muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)]",
                )}
              >
                {item.label}
              </Link>
            ))}
            <button className="rounded-md px-3 py-1.5 text-sm text-[var(--muted)] hover:bg-[var(--bg-hover)] inline-flex items-center gap-1">
              More <ChevronDown size={14} />
            </button>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <div className="relative flex items-center rounded-md border border-[var(--border)] overflow-hidden text-xs font-semibold">
              <button
                type="button"
                onClick={() => setEnv("test")}
                className={cn(
                  "px-2.5 py-1.5",
                  env === "test" ? "bg-[#f97316] text-black" : "text-[var(--muted)]",
                )}
              >
                TEST
              </button>
              <button
                type="button"
                title={liveEnabled ? "Live environment" : "Activate account to access live data."}
                onMouseEnter={() => !liveEnabled && setLiveTip(true)}
                onMouseLeave={() => setLiveTip(false)}
                onClick={() => {
                  if (!liveEnabled) {
                    setLiveTip(true);
                    router.push("/activate");
                    return;
                  }
                  setEnv("live");
                }}
                className={cn(
                  "px-2.5 py-1.5",
                  env === "live" ? "bg-[var(--live)] text-black" : "text-[var(--muted)]",
                  !liveEnabled && "opacity-60",
                )}
              >
                LIVE
              </button>
              {liveTip && !liveEnabled ? (
                <div className="absolute right-0 top-9 z-50 w-56 rounded-md border border-[var(--border)] bg-[var(--bg-elevated)] px-3 py-2 text-[11px] font-medium normal-case text-[var(--text)] shadow-[var(--popover-shadow)]">
                  Activate account to access live data.
                </div>
              ) : null}
            </div>
            <button className="hidden sm:inline-flex items-center gap-1 rounded-md border border-[var(--border)] px-2.5 py-1.5 text-sm text-[var(--muted)]">
              {orgName.slice(0, 22)}
              {orgName.length > 22 ? "…" : ""}
              <ChevronDown size={14} />
            </button>
            <NotificationsMenu />
            <HelpMenu />
            <ThemeMenu />
            <Link
              href="/settings/account"
              title="Settings"
              className="hidden sm:grid h-8 w-8 place-items-center rounded-md text-[var(--muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)]"
            >
              <Settings size={16} />
            </Link>
            <UserMenu name={userName} email={userEmail} />
          </div>
        </div>
      </header>

      <div className={cn("flex", showIntegrationSidebar ? "min-h-[calc(100vh-56px)]" : "")}>
        {showIntegrationSidebar && (
          <aside className="w-56 shrink-0 border-r border-[var(--border)] bg-[var(--bg-elevated)] p-3">
            <div className="px-2 pb-3 text-xs font-semibold tracking-wide text-[var(--muted)]">
              Integration
            </div>
            <div className="space-y-1">
              {INTEGRATION_NAV.map((item) => {
                const Icon = item.icon;
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex items-center gap-2 rounded-md px-2.5 py-2 text-sm",
                      active
                        ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                        : "text-[var(--muted)] hover:bg-[var(--bg-hover)] hover:text-white",
                    )}
                  >
                    <Icon size={16} />
                    {item.label}
                  </Link>
                );
              })}
            </div>
          </aside>
        )}
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}

export function Panel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-xl border border-[var(--border)] bg-[var(--bg-panel)]", className)}>
      {children}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description ? <p className="mt-1 text-sm text-[var(--muted)]">{description}</p> : null}
      </div>
      {actions}
    </div>
  );
}

export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "success" | "warning" | "accent" | "live" | "sandbox";
}) {
  const tones: Record<string, string> = {
    neutral: "bg-[#2a2f3a] text-[#c9d0db]",
    success: "bg-[rgba(34,197,94,0.15)] text-[var(--success)]",
    warning: "bg-[rgba(245,158,11,0.15)] text-[var(--warning)]",
    accent: "bg-[var(--accent-soft)] text-[var(--accent)]",
    live: "bg-[rgba(34,197,94,0.2)] text-[var(--live)]",
    sandbox: "bg-[rgba(249,115,22,0.2)] text-[var(--sandbox)]",
  };
  return (
    <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-xs font-semibold", tones[tone])}>
      {children}
    </span>
  );
}

export function ToolbarSearch({
  value,
  onChange,
  placeholder,
  actions,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-center gap-2">
      <div className="flex min-w-[240px] flex-1 items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg)] px-3 py-2">
        <Search size={16} className="text-[var(--muted)]" />
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full bg-transparent outline-none placeholder:text-[var(--muted)]"
        />
      </div>
      {actions}
    </div>
  );
}
