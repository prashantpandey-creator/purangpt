"use client";

import { DashboardShell } from "@/components/chat/DashboardShell";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <DashboardShell>{children}</DashboardShell>
  );
}
