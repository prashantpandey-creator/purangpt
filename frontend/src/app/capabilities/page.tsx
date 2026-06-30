import type { Metadata } from "next";
import { Navbar } from "@/components/landing/Navbar";
import { Capabilities } from "@/components/landing/Capabilities";
import { Footer } from "@/components/landing/Footer";

export const metadata: Metadata = {
  title: "Capabilities",
  description:
    "Discover what PuranGPT can do — natural-language search across the Puranas, Vedas, and epics with exact verse citations, deep research, and a guiding voice.",
  alternates: { canonical: "/capabilities" },
};

export default function CapabilitiesPage() {
  return (
    <main className="w-full bg-dark-900">
      <Navbar />
      <div className="pt-24">
        <Capabilities />
      </div>
      <Footer />
    </main>
  );
}
