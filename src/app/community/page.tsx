import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { CommunityFeed } from "@/components/community/CommunityFeed";

export const metadata = {
  title: "Community",
  description:
    "Ask questions, share wisdom, and discuss the sacred texts with fellow seekers on PuranGPT.",
};

export default function CommunityPage() {
  return (
    <>
      <Navbar />
      <main className="min-h-screen bg-[#0a0a0a] text-white">
        <CommunityFeed />
      </main>
      <Footer />
    </>
  );
}
