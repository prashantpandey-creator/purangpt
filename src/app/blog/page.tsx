import Link from "next/link";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

export const metadata = {
  title: "Blog",
};

export default function BlogPage() {
  return (
    <>
      <Navbar />
      <main className="pt-24 min-h-screen flex items-center">
        <div className="max-w-3xl mx-auto px-4 text-center">
          <h1 className="font-cinzel text-5xl font-bold text-gradient mb-6">
            Blog
          </h1>
          <p className="text-xl text-gray-300 mb-8">
            Articles coming soon. Stay tuned for insights on ancient wisdom and modern
            technology.
          </p>
          <div className="flex gap-4 justify-center">
            <Link href="/" className="btn-secondary">
              Back to Home
            </Link>
            <Link href="/chat" className="btn-primary">
              Sign Up Now
            </Link>
          </div>
        </div>
      </main>
      <Footer />
    </>
  );
}
