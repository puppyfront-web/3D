"use client";

// Workspace layout — renders the unified workspace TopNav for ALL workspace
// routes, including the canvas. The canvas page used to render its own
// full-screen chrome, but per the Enterprise Blueprint design (Stitch
// code_workspace.html) every workspace page shares the same top nav.

import { TopNav } from "@/components/layout/top-nav";
import { AuthGuard } from "@/components/auth-guard";

export default function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <div className="flex flex-col h-screen">
        <TopNav variant="workspace" />
        <main className="flex-1 overflow-hidden">{children}</main>
      </div>
    </AuthGuard>
  );
}
