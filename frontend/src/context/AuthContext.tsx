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
import { App } from "@capacitor/app";
import LogtoClient from "@logto/capacitor";
import { logtoCapacitorConfig } from "@/lib/logto";
import dynamic from "next/dynamic";

// Dynamic import breaks circular dependency: SignInModal → useAuth → AuthProvider → SignInModal
const SignInModal = dynamic(
  () => import("@/components/auth/SignInModal").then((m) => ({ default: m.SignInModal })),
  { ssr: false },
);

export interface AuthUser {
  sub: string;
  email: string;
  name: string;
  picture: string;
  provider?: string;
  display_name?: string | null;
  plan?: string;
  plan_status?: string;
  plan_current_period_end?: string | null;
}

interface AuthContextValue {
  user: AuthUser | null;
  profile: AuthUser | null;
  loading: boolean;
  initialized: boolean;
  configured: boolean;
  /** Direct Google OAuth. Opens our modal (email form) when called without "google". */
  signIn: (method?: "google", returnTo?: string) => Promise<void>;
  signInWithEmail: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  /** Programmatically open the sign-in modal. Use from any "Sign in" button. */
  openSignInModal: (returnTo?: string) => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// Singleton for Capacitor mobile auth
let mobileLogto: LogtoClient | null = null;
if (typeof window !== "undefined" && Capacitor.isNativePlatform()) {
  mobileLogto = new LogtoClient(logtoCapacitorConfig);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [profile, setProfile] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [initialized, setInitialized] = useState(false);
  const [signInModalOpen, setSignInModalOpen] = useState(false);
  const [signInModalReturnTo, setSignInModalReturnTo] = useState<string | undefined>();

  const fetchProfile = async () => {
    try {
      if (mobileLogto) {
        const isAuthenticated = await mobileLogto.isAuthenticated();
        if (isAuthenticated) {
          const userInfo = (await mobileLogto.fetchUserInfo()) as unknown as AuthUser;
          setUser(userInfo);
          setProfile(userInfo);
        } else {
          setUser(null);
          setProfile(null);
        }
      } else {
        const res = await fetch("/api/user/me");
        if (res.ok) {
          const data: AuthUser = await res.json();
          if (data && data.sub) {
            setUser(data);
            setProfile(data);
          } else {
            setUser(null);
            setProfile(null);
          }
        } else {
          setUser(null);
          setProfile(null);
        }
      }
    } catch (e) {
      console.error("Error fetching profile:", e);
      setUser(null);
      setProfile(null);
    } finally {
      setLoading(false);
      setInitialized(true);
    }
  };

  useEffect(() => {
    const handleCallback = async (url: string) => {
      if (mobileLogto) {
        try {
          await mobileLogto.handleSignInCallback(url);
        } catch {
          // Ignore — not a callback URL
        }
      }
      fetchProfile();
    };

    // For web
    handleCallback(window.location.href);

    // For mobile deep link callback
    let urlListener: any;
    if (Capacitor.isNativePlatform()) {
      App.addListener("appUrlOpen", (event: { url: string }) => {
        if (event.url.includes("callback")) {
          handleCallback(event.url);
        }
      }).then((listener) => {
        urlListener = listener;
      });
    }

    return () => {
      if (urlListener) {
        urlListener.remove();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Periodic session health check + silent refresh ────────────────────────
  // Google access tokens expire in ~1h while the session cookie lives 7 days.
  // Every 15 min: probe the token endpoint. If expired, try a silent refresh
  // using the stored refresh_token. Only log out if refresh also fails.
  useEffect(() => {
    if (!initialized || !user) return;

    const CHECK_INTERVAL = 15 * 60 * 1000; // 15 min
    const timer = setInterval(async () => {
      try {
        // 1. Quick probe — is the current access token still valid?
        const tokenProbe = await fetch("/api/logto/token");
        if (tokenProbe.ok) return; // still fresh

        // 2. Token expired — try silent refresh (Google refresh_token).
        //    The endpoint updates the session cookie on success.
        const refreshRes = await fetch("/api/auth/refresh", { method: "POST" });
        if (refreshRes.ok) {
          // Refresh succeeded — the cookie was updated. Reload the profile
          // so the UI reflects the fresh session.
          console.log("[auth] Session refreshed silently");
          await fetchProfile();
          return;
        }

        // 3. Refresh also failed — session is truly dead. Clear it.
        console.log("[auth] Session expired and refresh failed, clearing session");
        setUser(null);
        setProfile(null);
      } catch {
        // Network hiccup — don't log out on transient failures
      }
    }, CHECK_INTERVAL);

    return () => clearInterval(timer);
  }, [initialized, user]);

  const refreshProfile = useCallback(async () => {
    await fetchProfile();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /**
   * signIn — initiates authentication.
   * @param method  "google" → direct Google OAuth (no Logto UI).
   *                undefined → opens our custom SignInModal (email form).
   *                            The old Logto-hosted UI redirect has been removed.
   */
  const signIn = useCallback(
    async (method?: "google", returnTo?: string) => {
      if (mobileLogto) {
        await mobileLogto.signIn("com.fcpuru95.purangpt://callback");
        await fetchProfile();
        return;
      }

      if (method === "google") {
        // Direct Google OAuth — bypasses Logto entirely. No Logto-branded page.
        const url = returnTo
          ? `/api/auth/google?returnTo=${encodeURIComponent(returnTo)}`
          : "/api/auth/google";
        window.location.href = url;
        return;
      }

      // No method → open our custom sign-in modal with email form.
      // The Logto hosted UI redirect (/api/logto/sign-in) has been removed.
      setSignInModalReturnTo(returnTo);
      setSignInModalOpen(true);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [mobileLogto, fetchProfile],
  );

  const openSignInModal = useCallback((returnTo?: string) => {
    setSignInModalReturnTo(returnTo);
    setSignInModalOpen(true);
  }, []);

  /**
   * signInWithEmail — API-driven email/password sign-in (no Logto hosted UI).
   * Calls POST /api/auth/email; on success the backend sets the logto_session
   * cookie, so a subsequent fetchProfile picks up the new session.
   */
  const signInWithEmail = useCallback(
    async (email: string, password: string) => {
      if (mobileLogto) {
        await mobileLogto.signIn("com.fcpuru95.purangpt://callback");
        await fetchProfile();
        return;
      }

      const res = await fetch("/api/auth/email", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (!res.ok || !data.success) {
        throw new Error(data.error || "Sign in failed");
      }

      // Session cookie is set — refresh profile picks up the user
      await fetchProfile();
    },
    [mobileLogto, fetchProfile],
  );

  const signOut = useCallback(async () => {
    if (mobileLogto) {
      await mobileLogto.signOut("com.fcpuru95.purangpt://callback");
      setUser(null);
      setProfile(null);
    } else {
      // Clear both Google and Logto session cookies server-side
      await fetch("/api/auth/signout", { method: "POST" }).catch(() => {});
      window.location.href = "/api/logto/sign-out";
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        profile,
        loading,
        initialized,
        configured: true,
        signIn,
        signInWithEmail,
        signOut,
        refreshProfile,
        openSignInModal,
      }}
    >
      {children}
      {/* Single shared SignInModal — no duplicates in ChatInterface or UsageContext */}
      <SignInModal
        isOpen={signInModalOpen}
        onClose={() => setSignInModalOpen(false)}
        returnTo={signInModalReturnTo}
      />
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within <AuthProvider>");
  return ctx;
}
