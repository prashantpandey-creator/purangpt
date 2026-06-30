import type { Metadata } from "next";
import { Navbar } from "@/components/landing/Navbar";
import { Features } from "@/components/landing/Features";
import { WhyChooseUs } from "@/components/landing/WhyChooseUs";
import { Footer } from "@/components/landing/Footer";

export const metadata: Metadata = {
  title: "Features",
  description:
    "Explore PuranGPT's features — hybrid semantic search, exact verse citations, deep research mode, and a guiding voice rooted in the Hindu sacred tradition.",
  alternates: { canonical: "/features" },
};

export default function FeaturesPage() {
  return (
    <main className="w-full bg-dark-900">
      <Navbar />
      <div className="pt-24">
        <Features />
        <WhyChooseUs />
      </div>
      <Footer />
    </main>
  );
}
