"use client";

// Home / marketing landing — Linear-style dark canvas (`.theme-dark` scope).
// Composition: TopNav → Hero (split + real input panel) → HowItWorks →
// TeamRoster → ValueStrip → CaseSection → CtaBanner → slim footer.

import Link from "next/link";
import { BrainCircuit } from "lucide-react";
import { TopNav } from "@/components/layout/top-nav";
import { HeroSection } from "@/components/marketing/hero-section";
import { DecisionScene } from "@/components/marketing/decision-scene";
import { HowItWorks } from "@/components/marketing/how-it-works";
import { TeamRoster } from "@/components/marketing/team-roster";
import { ValueStrip } from "@/components/marketing/value-strip";
import { CaseSection } from "@/components/marketing/case-section";
import { CtaBanner } from "@/components/marketing/cta-banner";
import { APP_NAME, APP_FULL_NAME, APP_TAGLINE } from "@/lib/constants";

const FOOTER_LINKS = [
  { label: "团队工作台", href: "/workspace/projects" },
  { label: "案例库", href: "/admin/cases" },
  { label: "模板中心", href: "/admin/proposal-templates" },
  { label: "系统设置", href: "/admin/settings" },
];

export default function HomePage() {
  return (
    <div className="theme-dark min-h-screen bg-surface flex flex-col">
      <TopNav variant="marketing" activeHref="/" />
      <main className="w-full flex-1">
        <HeroSection />
        <DecisionScene />
        <HowItWorks />
        <TeamRoster />
        <ValueStrip />
        <CaseSection />
        <CtaBanner />
      </main>

      <footer className="border-t border-outline-variant py-10">
        <div className="max-w-container-max mx-auto px-margin-desktop flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex flex-col items-center md:items-start gap-2">
            <div className="font-medium text-on-surface flex items-center gap-2">
              <BrainCircuit className="h-5 w-5 text-primary" />
              <span>{APP_NAME}</span>
            </div>
            <p className="text-on-surface-variant text-xs">
              {APP_TAGLINE} · © {new Date().getFullYear()} {APP_FULL_NAME}
            </p>
          </div>
          <nav className="flex flex-wrap justify-center gap-6 text-xs">
            {FOOTER_LINKS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="text-on-surface-variant hover:text-on-surface transition-colors"
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      </footer>
    </div>
  );
}
