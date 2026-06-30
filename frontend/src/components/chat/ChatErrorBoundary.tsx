"use client";

import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  message?: string;
}

/**
 * Catches render-time crashes inside the chat shell and shows an on-brand
 * recovery screen instead of a blank page. Keeps the rest of the app (and the
 * user's stored conversations) intact — a reload re-mounts cleanly.
 */
export class ChatErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error?.message };
  }

  componentDidCatch(error: Error, info: unknown) {
    // Surface for debugging; swap for a real reporter (Sentry, etc.) later.
    console.error("[ChatErrorBoundary]", error, info);
  }

  handleReset = () => {
    this.setState({ hasError: false, message: undefined });
  };

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div
        className="flex h-full w-full flex-col items-center justify-center gap-6 px-6 text-center"
        style={{ background: "linear-gradient(135deg, #000000 0%, #0d0d0f 50%, #000000 100%)" }}
      >
        <div
          className="text-[5rem] leading-none select-none"
          style={{ color: "#e8b63f", opacity: 0.18 }}
          aria-hidden="true"
        >
          ॐ
        </div>
        <div className="max-w-md">
          <h2
            className="text-2xl"
            style={{ fontFamily: "var(--font-display)", color: "#f0dfb9" }}
          >
            Something interrupted the flow
          </h2>
          <p
            className="mt-3 text-sm leading-relaxed"
            style={{ fontFamily: "var(--font-body)", color: "#b9a18d" }}
          >
            An unexpected error stopped this view from rendering. Your
            conversations are saved — try again, or reload the page.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={this.handleReset}
            className="rounded-full px-5 py-2.5 text-sm transition-all hover:bg-[#e8b63f]/15"
            style={{
              border: "1px solid rgba(232,182,63,0.4)",
              color: "#e8b63f",
              fontFamily: "var(--font-ui)",
              background: "rgba(232,182,63,0.06)",
            }}
          >
            Try again
          </button>
          <button
            onClick={() => window.location.reload()}
            className="rounded-full px-5 py-2.5 text-sm transition-all hover:bg-white/10"
            style={{
              border: "1px solid rgba(255,255,255,0.12)",
              color: "#a38d7c",
              fontFamily: "var(--font-ui)",
            }}
          >
            Reload
          </button>
        </div>
      </div>
    );
  }
}
