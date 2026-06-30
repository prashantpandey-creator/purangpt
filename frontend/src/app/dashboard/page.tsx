import Link from "next/link";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

export const metadata = {
  title: "Dashboard",
};

export default function DashboardPage() {
  return (
    <>
      <Navbar />
      <main className="pt-24 min-h-screen flex items-center">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <h1
            className="text-5xl font-bold text-gradient mb-6"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Dashboard
          </h1>
          <p className="text-xl text-gray-300 mb-8">
            Your personal Vedic research hub.
          </p>
          <div className="flex gap-4 justify-center">
            <Link href="/chat" className="btn-primary">
              Open Chat
            </Link>
            <Link href="/dashboard/deep-research" className="btn-secondary">
              Deep Research
            </Link>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
