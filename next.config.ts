import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // compress MUST stay false: this app proxies the backend's /api/chat SSE stream
  // via the rewrite below. Next's gzip buffers the ENTIRE response to compress it,
  // so the browser saw ~17s of dead air then the whole answer at once instead of
  // tokens streaming as the Guru speaks. Verified: gzip → buffered (0s token span);
  // identity → streams. Static-asset compression, if wanted, belongs at Traefik
  // (its compress middleware correctly excludes text/event-stream).
  compress: false,
  poweredByHeader: false,

  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "*.supabase.co" },
      { protocol: "https", hostname: "avatars.githubusercontent.com" },
      { protocol: "https", hostname: "lh3.googleusercontent.com" },
    ],
    formats: ["image/avif", "image/webp"],
    minimumCacheTTL: 86400,
  },
  async redirects() {
    // The front door is the chat box. Everyone — signed-in or guest — is sent
    // straight to /chat at the ROUTING layer (a real 308, checked before the
    // filesystem per Next's redirects()), so there is no prerendered redirect
    // shell, no cached 200, and no client-side flash. A page-level redirect() on
    // the static "/" route instead prerenders a cached 200 HTML that redirects in
    // JS — works in a browser, but opaque to crawlers and slower. This is the
    // clean form. The old marketing page lives on at /welcome. 308 (permanent)
    // tells browsers and search engines the home moved to /chat for good — owner-
    // chosen for SEO. Trade-off: browsers cache a 308 hard, so reverting later
    // means a new path or a cache-bust, not just flipping this flag.
    return [{ source: "/", destination: "/chat", permanent: true }];
  },
  async headers() {
    // NEVER send immutable cache headers in development: Turbopack/Next rebuild
    // chunk graphs on every change, but `immutable` makes the browser keep
    // serving the OLD chunk for a year — which references modules from a dead
    // build and throws "module factory is not available" (surfacing as the
    // Cosmic Disturbance error boundary). Next itself warns about this. Only
    // apply the long-lived asset cache for production builds.
    if (process.env.NODE_ENV !== "production") return [];
    return [
      {
        // Cache static assets for 1 year
        source: "/_next/static/:path*",
        headers: [
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
      {
        // Cache fonts and images
        source: "/fonts/:path*",
        headers: [
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
    ];
  },
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || "http://backend:8000";
    return {
      fallback: [
        {
          source: "/api/:path*",
          destination: `${backendUrl}/api/:path*`,
        },
      ],
    };
  },
};

export default nextConfig;
