import type { Metadata } from "next";
import { Navbar } from "@/components/landing/Navbar";
import { FAQ } from "@/components/landing/FAQ";
import { Footer } from "@/components/landing/Footer";
import { JsonLd, faqSchema } from "@/components/seo/StructuredData";
import { getTranslation, type Translations } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "FAQ",
  description:
    "Frequently asked questions about PuranGPT — how it works, which sacred texts it covers, citation accuracy, pricing, and privacy.",
  alternates: { canonical: "/faq" },
};

// FAQPage JSON-LD, built server-side from the canonical English strings so the
// rich result is in the initial HTML and matches the visible accordion content.
// (The <FAQ> component renders the same Q&A, translated client-side.)
const FAQ_KEYS: { q: keyof Translations; a: keyof Translations }[] = [
  { q: "faq.q1", a: "faq.a1" },
  { q: "faq.q2", a: "faq.a2" },
  { q: "faq.q3", a: "faq.a3" },
  { q: "faq.q4", a: "faq.a4" },
  { q: "faq.q5", a: "faq.a5" },
  { q: "faq.q6", a: "faq.a6" },
  { q: "faq.q7", a: "faq.a7" },
  { q: "faq.q8", a: "faq.a8" },
  { q: "faq.q9", a: "faq.a9" },
];

export default function FAQPage() {
  const qa = FAQ_KEYS.map(({ q, a }) => ({
    question: getTranslation("en", q),
    answer: getTranslation("en", a),
  }));

  return (
    <main className="w-full bg-dark-900">
      <JsonLd schema={faqSchema(qa)} />
      <Navbar />
      <div className="pt-24">
        <FAQ />
      </div>
      <Footer />
    </main>
  );
}
