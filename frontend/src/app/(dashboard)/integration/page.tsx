"use client";

import Link from "next/link";
import { Building2, FormInput, Smartphone, Sparkles, Globe } from "lucide-react";
import { PageHeader, Panel, Badge } from "@/components/AppShell";

const CARDS = [
  {
    title: "No Code",
    desc: "A turn-key, no-code portal — nothing to build.",
    badge: "Immediate",
    tone: "success" as const,
    icon: Sparkles,
    href: "/workflows",
  },
  {
    title: "Hosted Solution",
    desc: "A hosted, fully customizable verification page.",
    badge: "Under 10 mins",
    tone: "success" as const,
    icon: FormInput,
    href: "/workflows",
  },
  {
    title: "Web",
    desc: "Drop our SDK straight into your own web app.",
    badge: "Under 30 mins",
    tone: "accent" as const,
    icon: Globe,
    href: "/integration/web",
  },
  {
    title: "Mobile",
    desc: "Native SDKs for iOS, Android and cross-platform.",
    badge: "Under 30 mins",
    tone: "accent" as const,
    icon: Smartphone,
    href: "/integration/mobile",
  },
  {
    title: "Other",
    desc: "Build a fully custom backend integration.",
    badge: "Varies",
    tone: "neutral" as const,
    icon: Building2,
    href: "/integration/api-docs",
  },
];

export default function IntegrationHomePage() {
  return (
    <div>
      <PageHeader
        title="Integrate with LivenCube"
        description="Our Integration Assistant helps you quickly and easily integrate LivenCube into your platform."
      />
      <p className="mb-4 text-sm text-[var(--muted)]">Choose your integration type:</p>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {CARDS.map((card) => {
          const Icon = card.icon;
          return (
            <Link key={card.title} href={card.href}>
              <Panel className="h-full p-5 transition hover:border-[var(--accent)]">
                <div className="mb-3 flex items-start justify-between">
                  <span className="grid h-10 w-10 place-items-center rounded-lg bg-[var(--accent-soft)] text-[var(--accent)]">
                    <Icon size={18} />
                  </span>
                  <Badge tone={card.tone}>{card.badge}</Badge>
                </div>
                <div className="text-lg font-semibold">{card.title}</div>
                <p className="mt-2 text-sm text-[var(--muted)]">{card.desc}</p>
              </Panel>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
