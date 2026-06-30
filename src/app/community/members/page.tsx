import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { MembersDirectory } from "@/components/community/MembersDirectory";

export const metadata = {
  title: "Members — Community",
  description:
    "See who has joined the PuranGPT community. Discover and follow fellow seekers exploring the sacred texts.",
};

export default function MembersPage() {
  return (
    <>
      <Navbar />
      <main className="min-h-screen bg-[#0a0a0a] text-white">
        <MembersDirectory />
      </main>
      <Footer />
    </>
  );
}
