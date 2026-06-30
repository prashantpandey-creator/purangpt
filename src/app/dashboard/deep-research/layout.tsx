"use client";

import { DashboardShell } from "@/components/chat/DashboardShell";

export default function DeepResearchLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <DashboardShell>{children}</DashboardShell>;
}
