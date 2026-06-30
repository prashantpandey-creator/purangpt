import type { Metadata } from "next";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { GrowthDashboard } from "./GrowthDashboard";

export const metadata: Metadata = {
  title: "Growth Engine",
  description:
    "Connect your social accounts and let PuranGPT generate and post marketing content on autopilot.",
  robots: { index: false, follow: false }, // private dashboard, keep out of search
};

export default function GrowthDashboardPage() {
  return (
    <>
      <Navbar />
      <main className="pt-24 pb-16 min-h-screen">
        <div className="max-w-5xl mx-auto px-4">
          <header className="mb-10">
            <span
              className="block text-[11px] uppercase tracking-[0.2em] text-[#f0cd80] mb-2"
              style={{ fontFamily: "var(--font-ui)" }}
            >
              The Autopilot
            </span>
            <h1
              className="text-4xl md:text-5xl text-gradient leading-tight"
              style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}
            >
              Growth Engine
            </h1>
            <p
              className="mt-3 text-base text-[#c7ae9a] max-w-2xl"
              style={{ fontFamily: "var(--font-body)" }}
            >
              Connect a channel once. The engine writes on-brand posts in your
              voice, checks each one, and publishes where automation is allowed —
              queueing the rest for your one-tap approval.
            </p>
          </header>
          <GrowthDashboard />
        </div>
      </main>
      <Footer />
    </>
  );
}
