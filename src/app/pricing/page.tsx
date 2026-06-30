"use client";

import { useEffect, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { Navbar } from "@/components/landing/Navbar";
import { Pricing } from "@/components/landing/Pricing";
import { Footer } from "@/components/landing/Footer";
import { useAuth } from "@/context/AuthContext";

export default function PricingPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { refreshProfile } = useAuth();
  const handled = useRef(false);

  useEffect(() => {
    if (handled.current) return;
    const success = searchParams.get("success");
    const cancel = searchParams.get("cancel");

    if (success === "true") {
      handled.current = true;
      // Stripe redirected back after successful checkout — refresh profile so
      // the navbar/UI reflects Pro status, then redirect to chat with upgrade flag.
      refreshProfile().then(() => {
        router.replace("/chat?upgraded=1");
      });
    } else if (cancel === "true") {
      handled.current = true;
      // Just clean up the URL — user stays on pricing page
      router.replace("/pricing");
    }
  }, [searchParams, refreshProfile, router]);

  return (
    <main className="w-full bg-dark-900">
      <Navbar />
      <div className="pt-24">
        <Pricing />
      </div>
      <Footer />
    </main>
  );
}
