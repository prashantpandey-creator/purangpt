import Link from "next/link";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

export const metadata = {
  title: "System Status",
};

export default function StatusPage() {
  return (
    <>
      <Navbar />
      <main className="pt-24 min-h-screen flex items-center">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <h1 className="font-cinzel text-5xl font-bold text-gradient mb-6">
            System Status
          </h1>
          <div className="mb-8">
            <div className="flex items-center justify-center gap-3 mb-4">
              <div className="w-3 h-3 rounded-full bg-green-500 animate-pulse" />
              <p className="text-xl text-gray-300">All systems operational</p>
            </div>
            <p className="text-gray-400 text-sm">
              Last updated: {new Date().toLocaleString()}
            </p>
          </div>
          <div className="flex gap-4 justify-center">
            <Link href="/" className="btn-secondary">
              Back to Home
            </Link>
            <Link href="/chat" className="btn-primary">
              Get Started
            </Link>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
