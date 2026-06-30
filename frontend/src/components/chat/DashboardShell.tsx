"use client";

import { useEffect } from "react";
import { Menu } from "lucide-react";
import { useUI } from "@/context/UIPreferencesContext";
import { Sidebar } from "./Sidebar";
import { CosmicHum } from "./CosmicHum";
import { ChatErrorBoundary } from "./ChatErrorBoundary";
import { ConnectionBanner } from "./ConnectionBanner";

// The chat shell. There is NO top toolbar — every control (collapse, Nāda,
// account, navigation) lives in the left drawer, which collapses to an icon
// rail on desktop and slides away on mobile. The main column is pure canvas
// over the living void.
export function DashboardShell({ children }: { children: React.ReactNode }) {
  const { sidebarOpen, toggleSidebar, setSidebarOpen } = useUI();

  // On mobile, always start with the sidebar closed.
  useEffect(() => {
    if (window.innerWidth < 1024) {
      setSidebarOpen(false);
    }
  }, [setSidebarOpen]);

  return (
    <div className="chat-shell flex overflow-hidden">
      {/* The background is now managed by the specific page (e.g., ChatInterface uses DarshanVoid) */}
      <CosmicHum />

      {/* Mobile overlay — tap to close */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 lg:hidden bg-black/60 backdrop-blur-sm"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar:
          - Mobile: fixed overlay, slides in/out via translate
          - Desktop (lg+): always visible, static in layout; width comes from
            the drawer itself (icon rail when collapsed) */}
      <div
        className={`
          fixed inset-y-0 left-0 z-50 flex flex-col
          transition-transform duration-300 ease-in-out
          lg:relative lg:z-20 lg:translate-x-0 lg:flex-shrink-0
          ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}
        `}
        style={{ height: "100dvh" }}
      >
        <Sidebar />
      </div>

      {/* Main content — sits above the void (z-10); backgrounds are
          transparent so the field shows through the whole experience. */}
      <div className="relative z-10 flex-1 flex flex-col overflow-hidden min-w-0">
        <ConnectionBanner />

        <div className="flex-1 overflow-hidden relative">
          <ChatErrorBoundary>{children}</ChatErrorBoundary>

          {/* Mobile-only reopener — the drawer's controls live inside it, so on
              desktop the in-rail expand button handles this. */}
          {!sidebarOpen && (
            <button
              onClick={toggleSidebar}
              className="lg:hidden absolute top-3 left-3 z-40 flex h-9 w-9 items-center justify-center rounded-full transition-all active:scale-95 animate-fade-in"
              style={{
                background: "rgba(8, 7, 6, 0.72)",
                backdropFilter: "blur(14px)",
                WebkitBackdropFilter: "blur(14px)",
                border: "1px solid rgba(232,182,63,0.22)",
                color: "#e8b63f",
                boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
                paddingTop: "max(0px, env(safe-area-inset-top, 0px))",
              }}
              aria-label="Open menu"
            >
              <Menu className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
