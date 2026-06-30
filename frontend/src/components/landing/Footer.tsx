"use client";

import Link from "next/link";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation, type Translations } from "@/lib/i18n";

export function Footer() {
  const { language } = useLanguage();
  const currentYear = new Date().getFullYear();

  const linkGroups: {
    titleKey: keyof Translations;
    items: { nameKey: keyof Translations; href: string }[];
  }[] = [
    {
      titleKey: "ftr.col_product",
      items: [
        { nameKey: "ftr.product.features", href: "#features" },
        { nameKey: "ftr.product.pricing", href: "#pricing" },
        { nameKey: "ftr.product.download", href: "/api/logto/sign-in" },
        { nameKey: "ftr.product.api_docs", href: "/docs" },
      ],
    },
    {
      titleKey: "ftr.col_company",
      items: [
        { nameKey: "ftr.company.about", href: "/about" },
        { nameKey: "ftr.company.blog", href: "/blog" },
        { nameKey: "ftr.company.press", href: "/about" },
        { nameKey: "ftr.company.careers", href: "/careers" },
      ],
    },
    {
      titleKey: "ftr.col_resources",
      items: [
        { nameKey: "ftr.resources.transparency", href: "/transparency" },
        { nameKey: "ftr.resources.documentation", href: "/docs" },
        { nameKey: "ftr.resources.community", href: "/community" },
        { nameKey: "ftr.resources.faq", href: "#faq" },
        { nameKey: "ftr.resources.status", href: "/status" },
      ],
    },
    {
      titleKey: "ftr.col_legal",
      items: [
        { nameKey: "ftr.legal.privacy", href: "/privacy" },
        { nameKey: "ftr.legal.terms", href: "/terms" },
        { nameKey: "ftr.legal.refund", href: "/refund" },
        { nameKey: "ftr.legal.contact", href: "/contact" },
      ],
    },
  ];

  return (
    <footer className="w-full bg-dark-900 border-t border-gray-700">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        {/* Main Footer Content */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-8 mb-12">
          {/* Brand */}
          <div className="col-span-2 md:col-span-1">
            <h3 className="text-xl font-bold font-cinzel text-gradient mb-2">
              PuranGPT
            </h3>
            <p className="text-gray-400 text-sm">
              {getTranslation(language, "ftr.tagline")}
            </p>
          </div>

          {/* Links */}
          {linkGroups.map((group) => (
            <div key={group.titleKey}>
              <h4 className="text-sm font-semibold text-white uppercase tracking-wide mb-4">
                {getTranslation(language, group.titleKey)}
              </h4>
              <ul className="space-y-2">
                {group.items.map((item) => (
                  <li key={item.nameKey}>
                    <Link
                      href={item.href}
                      className="text-gray-400 hover:text-saffron transition-colors text-sm"
                    >
                      {getTranslation(language, item.nameKey)}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Divider */}
        <div className="border-t border-gray-700 pt-8 mt-8">
          {/* Social + Copyright */}
          <div className="flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-gray-400 text-sm">
              © {currentYear} {getTranslation(language, "ftr.copyright")}
            </p>

            {/* Social Links */}
            <div className="flex gap-4">
              <a
                href="https://github.com/prashantpandey-creator/purangpt"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-400 hover:text-saffron transition-colors"
                title="GitHub"
                aria-label="PuranGPT on GitHub"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v 3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                </svg>
              </a>
              <a
                href="https://x.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-gray-400 hover:text-saffron transition-colors"
                title="X (Twitter)"
                aria-label="PuranGPT on X (formerly Twitter)"
              >
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24h-6.6l-5.168-6.759-5.933 6.759h-3.308l7.739-8.835-8.158-10.665h6.75l4.967 6.59 5.528-6.59zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                </svg>
              </a>
              <a
                href="mailto:fcpuru95@gmail.com"
                className="text-gray-400 hover:text-saffron transition-colors"
                title="Email"
                aria-label="Email PuranGPT"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
