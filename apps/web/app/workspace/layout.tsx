"use client";

import { Header } from "@/components/layout/header";

export default function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col h-screen">
      <Header title="工作台" />
      <div className="flex-1 overflow-y-auto">{children}</div>
    </div>
  );
}
