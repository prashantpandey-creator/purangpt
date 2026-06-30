"use client";

import { useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";

/**
 * Wraps auth pages (login/signup/...). If the user is already authenticated,
 * redirect them away (to ?next or /chat) instead of showing the form.
 */
export function RedirectIfAuthed({ children }: { children: React.ReactNode }) {
  const { user, initialized } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    if (initialized && user) {
      const next = searchParams.get("next");
      router.replace(next && next.startsWith("/") ? next : "/chat");
    }
  }, [initialized, user, router, searchParams]);

  return <>{children}</>;
}
