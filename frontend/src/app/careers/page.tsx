import Link from "next/link";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

export const metadata = {
  title: "Careers",
};

export default function CareersPage() {
  return (
    <>
      <Navbar />
      <main className="pt-24 min-h-screen flex items-center">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <h1 className="font-cinzel text-5xl font-bold text-gradient mb-6">
            Careers
          </h1>
          <p className="text-xl text-gray-300 mb-8">
            We're not hiring yet, but we're growing! Check back soon for exciting
            opportunities to join our team.
          </p>
          <div className="flex gap-4 justify-center">
            <Link href="/" className="btn-secondary">
              Back to Home
            </Link>
            <Link href="/chat" className="btn-primary">
              Explore PuranGPT
            </Link>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
