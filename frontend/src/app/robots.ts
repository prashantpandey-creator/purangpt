import type { MetadataRoute } from "next";

export const dynamic = "force-static";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/chat", "/auth", "/settings", "/profile", "/api"],
    },
    sitemap: "https://purangpt.com/sitemap.xml",
  };
}
