"use client";

// Workspace layout — passthrough for chat pages,
// adds header for legacy project detail pages.
export default function WorkspaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
