"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  ReactNode,
} from "react";
import { Capacitor } from "@capacitor/core";
import { NativePaywall } from "@/components/mobile/NativePaywall";
import { useSubscription } from "@/context/SubscriptionContext";

interface PaywallContextType {
  // Opens the native IAP paywall (native) or navigates to /pricing (web).
  openPaywall: () => void;
}

const PaywallContext = createContext<PaywallContextType>({
  openPaywall: () => {},
});

export function PaywallProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const { isPro } = useSubscription();

  // Avoid hydration mismatch — Capacitor.isNativePlatform() is always false
  // on the server, so we gate rendering until the client is ready.
  useEffect(() => setMounted(true), []);

  const openPaywall = useCallback(() => {
    if (isPro) return;
    if (Capacitor.isNativePlatform()) {
      setIsOpen(true);
    } else {
      window.location.href = "/pricing";
    }
  }, [isPro]);

  return (
    <PaywallContext.Provider value={{ openPaywall }}>
      {children}
      {mounted && Capacitor.isNativePlatform() && (
        <NativePaywall isOpen={isOpen} onClose={() => setIsOpen(false)} />
      )}
    </PaywallContext.Provider>
  );
}

export function usePaywall() {
  return useContext(PaywallContext);
}
