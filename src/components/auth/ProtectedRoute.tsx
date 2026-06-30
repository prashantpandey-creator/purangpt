"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { SignInModal } from "@/components/auth/SignInModal";

function FullScreenSpinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex h-screen w-full flex-col items-center justify-center bg-[#000000] text-[#e8b63f]">
      <div className="mb-4 h-8 w-8 animate-spin rounded-full border-2 border-current border-t-transparent"></div>
      <p className="text-sm uppercase tracking-widest text-[#a38d7c]" style={{ fontFamily: "var(--font-geist, sans-serif)" }}>
        {label}
      </p>
    </div>
  );
}

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, initialized } = useAuth();
  const [showModal, setShowModal] = useState(false);

  useEffect(() => {
    // Once auth is initialized and we confirm no user exists, show the login modal
    if (initialized && !user) {
      setShowModal(true);
    } else {
      setShowModal(false);
    }
  }, [initialized, user]);

  if (!initialized) {
    return <FullScreenSpinner />;
  }

  if (!user) {
    return (
      <div className="flex h-screen w-full flex-col items-center justify-center bg-[#000000]">
        <SignInModal isOpen={showModal} onClose={() => {
          // If they close the modal without logging in, redirect them home
          window.location.href = '/';
        }} />
      </div>
    );
  }

  return <>{children}</>;
}
