import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";
import { PostDetail } from "@/components/community/PostDetail";

export const metadata = {
  title: "Discussion · Community",
};

export default async function CommunityPostPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const postId = Number(id);

  return (
    <>
      <Navbar />
      <main className="min-h-screen bg-[#0a0a0a] text-white">
        {Number.isInteger(postId) ? (
          <PostDetail postId={postId} />
        ) : (
          <div className="mx-auto max-w-3xl px-4 py-24 text-center text-gray-300">
            Invalid post.
          </div>
        )}
      </main>
      <Footer />
    </>
  );
}
