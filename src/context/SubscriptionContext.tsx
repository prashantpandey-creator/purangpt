"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { useAuth } from "./AuthContext";
import { Capacitor } from "@capacitor/core";
import { PurangptIAP, type IAPOfferings, type IAPPackage } from "@/lib/iap/PurangptIAP";

interface SubscriptionContextType {
  isPro: boolean;
  offerings: IAPOfferings | null;
  purchasePackage: (pkg: IAPPackage) => Promise<boolean>;
  restorePurchases: () => Promise<boolean>;
  isLoading: boolean;
}

const SubscriptionContext = createContext<SubscriptionContextType>({
  isPro: false,
  offerings: null,
  purchasePackage: async () => false,
  restorePurchases: async () => false,
  isLoading: true,
});

const PRO_PLANS = ["pro", "scholar", "admin"];

/**
 * Sends a signed StoreKit JWS to the backend, which verifies it against Apple's
 * certs and grants the Pro role in the subscriptions table. Returns the backend
 * truth for isPro. Falls back to the optimistic client value on network error.
 */
async function verifyWithBackend(jws: string): Promise<boolean | null> {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
    const deviceId =
      typeof localStorage !== "undefined"
        ? localStorage.getItem("purangpt_device_id") || ""
        : "";

    // Attach auth bearer so the FastAPI require_auth dependency passes.
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "X-Device-ID": deviceId,
    };
    try {
      const tokenRes = await fetch("/api/logto/token");
      if (tokenRes.ok) {
        const { token } = await tokenRes.json();
        if (token) headers["Authorization"] = `Bearer ${token}`;
      }
    } catch { /* unauthenticated — the verify call will return 401 */ }

    const res = await fetch(`${apiUrl}/api/iap/apple/verify`, {
      method: "POST",
      headers,
      credentials: "include",
      body: JSON.stringify({ jws }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return Boolean(data.is_pro ?? data.isPro);
  } catch {
    return null;
  }
}

export function SubscriptionProvider({ children }: { children: ReactNode }) {
  const [isPro, setIsPro] = useState(false);
  const [offerings, setOfferings] = useState<IAPOfferings | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const { user } = useAuth();

  // Native init — load products + start listening for transaction updates.
  // StoreKit plugin is iOS-only; web and Android read Pro from user.plan.
  useEffect(() => {
    if (!Capacitor.isNativePlatform() || Capacitor.getPlatform() !== "ios") {
      return;
    }

    let removeListener: (() => Promise<void>) | undefined;

    async function init() {
      try {
        const fetched = await PurangptIAP.getOfferings();
        setOfferings(fetched);
        const ent = await PurangptIAP.getEntitlements();
        setIsPro(ent.isPro);
      } catch (e) {
        console.error("[IAP] init failed", e);
      } finally {
        setIsLoading(false);
      }

      // Re-sync whenever StoreKit reports a transaction change (renewal, etc.)
      const handle = await PurangptIAP.addListener("transactionUpdate", async () => {
        try {
          const ent = await PurangptIAP.getEntitlements();
          if (ent.jws) {
            const backendPro = await verifyWithBackend(ent.jws);
            setIsPro(backendPro ?? ent.isPro);
          } else {
            setIsPro(ent.isPro);
          }
        } catch (e) {
          console.error("[IAP] transactionUpdate sync failed", e);
        }
      });
      removeListener = handle.remove;
    }

    init();
    return () => {
      removeListener?.();
    };
  }, []);

  // Web / Android: map plan from the authenticated profile.
  useEffect(() => {
    if (Capacitor.isNativePlatform() && Capacitor.getPlatform() === "ios") {
      return;
    }
    const hasPro = user ? PRO_PLANS.includes(user.plan ?? "free") : false;
    setIsPro(hasPro);
    setIsLoading(false);
  }, [user]);

  const purchasePackage = async (pkg: IAPPackage): Promise<boolean> => {
    if (!Capacitor.isNativePlatform() || Capacitor.getPlatform() !== "ios") return false;
    try {
      const result = await PurangptIAP.purchasePackage({ productId: pkg.identifier });
      if (!result.success) return false;
      // Backend is authoritative; optimistically set Pro if it's unreachable.
      if (result.jws) {
        const backendPro = await verifyWithBackend(result.jws);
        const finalPro = backendPro ?? true;
        setIsPro(finalPro);
        return finalPro;
      }
      setIsPro(true);
      return true;
    } catch (e) {
      console.error("[IAP] purchase failed", e);
      return false;
    }
  };

  const restorePurchases = async (): Promise<boolean> => {
    if (!Capacitor.isNativePlatform() || Capacitor.getPlatform() !== "ios") return false;
    try {
      const result = await PurangptIAP.restorePurchases();
      if (!result.success) {
        setIsPro(false);
        return false;
      }
      if (result.jws) {
        const backendPro = await verifyWithBackend(result.jws);
        const finalPro = backendPro ?? true;
        setIsPro(finalPro);
        return finalPro;
      }
      setIsPro(true);
      return true;
    } catch (e) {
      console.error("[IAP] restore failed", e);
      return false;
    }
  };

  return (
    <SubscriptionContext.Provider value={{ isPro, offerings, purchasePackage, restorePurchases, isLoading }}>
      {children}
    </SubscriptionContext.Provider>
  );
}

export function useSubscription() {
  return useContext(SubscriptionContext);
}
