import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { ProfileView } from "@/components/community/ProfileView";

export const metadata = {
  title: "Member · Community",
};

export default async function CommunityProfilePage({
  params,
}: {
  params: Promise<{ sub: string }>;
}) {
  const { sub } = await params;
  const userSub = decodeURIComponent(sub);

  return (
    <>
      <Navbar />
      <main className="min-h-screen bg-[#0a0a0a] text-white">
        <ProfileView userSub={userSub} />
      </main>
      <Footer />
    </>
  );
}
