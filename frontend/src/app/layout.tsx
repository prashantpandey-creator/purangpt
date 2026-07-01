import type { Metadata, Viewport } from "next";
import { Inter, Geist, Marcellus, Quicksand } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import { UIPreferencesProvider } from "@/context/UIPreferencesContext";
import { ChatPreferencesProvider } from "@/context/ChatPreferencesContext";
import { ConversationProvider } from "@/context/ConversationContext";
import { ToastProvider } from "@/context/ToastContext";
import { SubscriptionProvider } from "@/context/SubscriptionContext";
import { PaywallProvider } from "@/context/PaywallContext";
import { UsageProvider } from "@/context/UsageContext";
import { LanguageProvider } from "@/context/LanguageContext";


import { SoundProvider } from "@/components/SoundProvider";
import { SiteStructuredData } from "@/components/seo/StructuredData";
import PersistentBackground from "@/components/chat/PersistentBackground";

const marcellus = Marcellus({
  variable: "--font-marcellus",
  weight: "400",
  subsets: ["latin"],
  display: "swap",
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
});

const geist = Geist({
  variable: "--font-geist",
  subsets: ["latin"],
  display: "swap",
});

// Warm, curvy companion face — used for the side panel so the navigation reads
// soft and inviting rather than the cold, wide-tracked monospace it used before.
const quicksand = Quicksand({
  variable: "--font-sidebar",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL("https://purangpt.com"),
  title: {
    default: "PuranGPT — Vedic Research AI",
    template: "%s · PuranGPT",
  },
  description:
    "Explore the 18 Mahapuranas, Vedas, Upanishads, and Yogic texts through natural language conversations with exact verse citations.",
  keywords: [
    "Puranas",
    "Vedas",
    "Upanishads",
    "Bhagavad Gita",
    "Sanskrit",
    "Hindu scriptures",
    "AI",
    "RAG",
    "verse citations",
    "Ramayana",
    "Mahabharata",
    "spiritual AI",
  ],
  authors: [{ name: "PuranGPT" }],
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "PuranGPT — Vedic Research AI",
    description:
      "AI-powered access to Hindu sacred texts with exact verse citations.",
    url: "https://purangpt.com",
    siteName: "PuranGPT",
    locale: "en_US",
    type: "website",
    images: [
      {
        url: "/logo-v7.png",
        width: 512,
        height: 512,
        alt: "PuranGPT — Vedic Research AI",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "PuranGPT",
    description:
      "AI-powered access to Hindu sacred texts with exact verse citations.",
    images: ["/logo-v7.png"],
  },
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "PuranGPT",
    startupImage: ["/apple-touch-icon.png"],
  },
  icons: {
    icon: "/favicon.ico",
    apple: "/apple-touch-icon.png",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
  interactiveWidget: "resizes-content",
  themeColor: "#000000",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark" style={{ backgroundColor: "#000000" }} suppressHydrationWarning>
      <head>
        {/* Capacitor WebView detection — disables backdrop-filter (iOS WKWebView's
            worst perf trap). Must run BEFORE first paint to avoid FOUC. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){if(typeof window.Capacitor!=='undefined'||navigator.userAgent.includes('Capacitor')){document.documentElement.classList.add('capacitor-app')}})()`,
          }}
        />
      </head>
      <body
        className={`${inter.variable} ${geist.variable} ${marcellus.variable} ${quicksand.variable} font-sans antialiased bg-black text-[#e8e1d4]`}
      >
        <PersistentBackground />
        <SoundProvider />
        <SiteStructuredData />
        <LanguageProvider>
          <AuthProvider>
            <SubscriptionProvider>
              <PaywallProvider>
              <UsageProvider>
              <UIPreferencesProvider>
                <ChatPreferencesProvider>
                <ConversationProvider>
                  <ToastProvider>
                    {children}
                  </ToastProvider>
                </ConversationProvider>
                </ChatPreferencesProvider>
              </UIPreferencesProvider>
              </UsageProvider>
              </PaywallProvider>
            </SubscriptionProvider>
          </AuthProvider>
        </LanguageProvider>
      </body>
    </html>
  );
}
