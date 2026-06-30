/**
 * StructuredData — JSON-LD schema.org markup for rich Google results.
 *
 * ADDITIVE & SAFE: this is a pure server component that renders a single
 * <script type="application/ld+json"> tag. It ships ZERO client JavaScript,
 * touches no existing component, and cannot alter any runtime behaviour of the
 * app. Removing it reverts SEO to exactly today's state.
 *
 * What it buys us:
 *  - Organization  → brand knowledge panel, logo in results
 *  - WebSite + SearchAction → the Google "sitelinks search box" under our result
 *  - SoftwareApplication → eligibility for the app rich result (rating, price)
 *
 * Per-page schemas (FAQPage, Article, BreadcrumbList) are emitted by the
 * <JsonLd> primitive below so any route can drop one in without re-stringifying.
 */

const SITE_URL = "https://purangpt.com";

/** Low-level primitive: stringify one schema object into a JSON-LD script tag. */
export function JsonLd({ schema }: { schema: Record<string, unknown> }) {
  return (
    <script
      type="application/ld+json"
      // JSON.stringify output is safe here: it is our own data, not user input,
      // and Next renders this on the server. We escape "<" defensively anyway.
      dangerouslySetInnerHTML={{
        __html: JSON.stringify(schema).replace(/</g, "\\u003c"),
      }}
    />
  );
}

/**
 * Site-wide structured data. Mount ONCE (in the root layout, inside <body>).
 * `sameAs` is intentionally empty until the real social profile URLs exist —
 * fill it in rather than inventing handles.
 */
export function SiteStructuredData() {
  const organization = {
    "@context": "https://schema.org",
    "@type": "Organization",
    "@id": `${SITE_URL}/#organization`,
    name: "PuranGPT",
    url: SITE_URL,
    logo: {
      "@type": "ImageObject",
      url: `${SITE_URL}/icon-512.png`,
      width: 512,
      height: 512,
    },
    description:
      "AI-powered research assistant for the Hindu sacred texts — the 18 Mahapuranas, Vedas, Upanishads, Ramayana, Mahabharata, and Yogic scriptures — answering in natural language with exact verse citations.",
    sameAs: [] as string[], // TODO: add X, Telegram, Instagram, YouTube URLs when live
  };

  const website = {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "@id": `${SITE_URL}/#website`,
    url: SITE_URL,
    name: "PuranGPT",
    publisher: { "@id": `${SITE_URL}/#organization` },
    description:
      "Explore the Puranas, Vedas, Upanishads, and Yogic texts through conversation, with exact verse citations.",
    potentialAction: {
      "@type": "SearchAction",
      target: {
        "@type": "EntryPoint",
        urlTemplate: `${SITE_URL}/?q={search_term_string}`,
      },
      "query-input": "required name=search_term_string",
    },
  };

  const application = {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "PuranGPT",
    applicationCategory: "EducationApplication",
    operatingSystem: "Web, iOS, Android",
    url: SITE_URL,
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
      description: "Free tier with optional Pro subscription.",
    },
    description:
      "Converse with the Hindu sacred corpus and receive answers grounded in exact verse citations.",
  };

  return (
    <>
      <JsonLd schema={organization} />
      <JsonLd schema={website} />
      <JsonLd schema={application} />
    </>
  );
}

/** Build an FAQPage schema from a list of Q&A pairs. */
export function faqSchema(qa: { question: string; answer: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: qa.map(({ question, answer }) => ({
      "@type": "Question",
      name: question,
      acceptedAnswer: { "@type": "Answer", text: answer },
    })),
  };
}

/** Build an Article schema (for blog posts / scripture pages). */
export function articleSchema(opts: {
  headline: string;
  description: string;
  url: string;
  datePublished?: string;
  dateModified?: string;
  image?: string;
}) {
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: opts.headline,
    description: opts.description,
    url: opts.url,
    image: opts.image ?? `${SITE_URL}/icon-512.png`,
    datePublished: opts.datePublished,
    dateModified: opts.dateModified ?? opts.datePublished,
    author: { "@type": "Organization", name: "PuranGPT" },
    publisher: { "@id": `${SITE_URL}/#organization` },
  };
}

/** Build a BreadcrumbList schema for nested pages. */
export function breadcrumbSchema(items: { name: string; url: string }[]) {
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: item.name,
      item: item.url,
    })),
  };
}
