import { redirect } from "next/navigation";

/**
 * The front door is the chat box itself.
 *
 * Everyone — signed-in or guest — lands directly in /chat (an open route; the
 * device-ID guest path lets visitors converse before signing in). From there the
 * sidebar's "Explore" rail carries every other doorway: Voice Darshan, the Sacred
 * Library, Community, Workspace, Deep Research, About.
 *
 * Server-side redirect → instant, no client flash, no marketing detour. The old
 * marketing front page is preserved and still reachable at /welcome.
 */
export default function Home() {
  redirect("/chat");
}
