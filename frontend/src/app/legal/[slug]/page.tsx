import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

const contentMap: Record<
  string,
  { title: string; description: string; body: string[] }
> = {
  privacy: {
    title: "Privacy Policy",
    description:
      "How PuranGPT collects, uses, and protects your information when you use our Vedic research service.",
    body: [
      "Your privacy is important to us. This Privacy Policy explains how we collect, use, disclose, and otherwise handle your information when you use our website and services.",
      "We collect information you provide directly to us, such as when you create an account, subscribe to our service, or contact us for support. This includes your name, email address, and any other information you choose to provide.",
      "We use the information we collect to provide, maintain, and improve our services, to send you technical notices and support messages, and to respond to your inquiries and requests.",
      "We may share your information with third-party service providers who perform services on our behalf, including hosting providers, payment processors, and analytics services.",
      "We implement appropriate technical and organizational security measures to protect your information against unauthorized access, alteration, disclosure, or destruction.",
      "If you have any questions about this Privacy Policy, please contact us at privacy@purangpt.com.",
    ],
  },
  terms: {
    title: "Terms of Service",
    description:
      "The terms and conditions governing your use of PuranGPT's website and Hindu sacred-text research service.",
    body: [
      "Welcome to PuranGPT. These Terms of Service govern your use of our website and services. By accessing and using PuranGPT, you accept and agree to be bound by all the terms and conditions of this agreement.",
      "You agree to use PuranGPT only for lawful purposes and in a way that does not infringe on the rights of others or restrict their use and enjoyment of PuranGPT.",
      "Prohibited behavior includes harassing or causing distress or inconvenience to any person, transmitting obscene or offensive content, or disrupting the normal flow of dialogue within PuranGPT.",
      "The content and materials on PuranGPT are provided on an 'as is' basis. We do not warrant the accuracy, completeness, or usefulness of this information. Your use of any information or materials on this website is entirely at your own risk.",
      "We shall not be liable to you in relation to the contents of or use of PuranGPT. This is a comprehensive limitation of liability that applies to all damages of any kind, including compensatory, direct, indirect, or consequential damages.",
      "These Terms of Service are governed by and construed in accordance with the laws of the jurisdiction where we operate.",
    ],
  },
  license: {
    title: "License Information",
    description:
      "Source attribution and usage licensing for the sacred texts, translations, and software behind PuranGPT.",
    body: [
      "The content available through PuranGPT is derived from various public domain and licensed sources. We have made efforts to respect intellectual property rights and provide proper attribution where applicable.",
      "The sacred texts and translations included in our service are sourced from verified public domain collections, including texts from archive.org, sacred-texts.com, and GRETIL.",
      "Users are granted a limited license to access and use PuranGPT for personal, non-commercial purposes. You may not reproduce, distribute, or transmit any content without prior written permission from PuranGPT.",
      "The PuranGPT software and design are protected by copyright. You may not modify, reverse engineer, or create derivative works based on our software.",
      "If you believe your intellectual property rights have been violated, please contact us immediately at legal@purangpt.com with evidence of the violation.",
      "We reserve the right to update our licensing terms and will provide notice of any significant changes.",
    ],
  },
  cookies: {
    title: "Cookie Policy",
    description:
      "How PuranGPT uses cookies and tracking technologies, and how you can control them.",
    body: [
      "PuranGPT uses cookies and similar tracking technologies to enhance your experience on our website. Cookies are small files stored on your device that help us remember your preferences and understand how you use our service.",
      "We use session cookies to maintain your login status and provide a seamless experience while you navigate our site. These cookies expire when you close your browser.",
      "We use persistent cookies to remember your preferences, such as your theme selection and language preferences, across multiple visits.",
      "Third-party services, including analytics providers and payment processors, may also place cookies on your device. We do not control these cookies, and we encourage you to review their privacy policies.",
      "Most web browsers allow you to control cookies through their settings. You can delete existing cookies or set your browser to refuse new cookies. However, disabling cookies may affect your ability to use certain features of PuranGPT.",
      "For more information about how we use cookies and your options, please contact us at cookies@purangpt.com.",
    ],
  },
};

export async function generateStaticParams() {
  return [
    { slug: "privacy" },
    { slug: "terms" },
    { slug: "license" },
    { slug: "cookies" },
  ];
}

// Hard-404 any slug outside the four real legal pages (no soft-200 phantoms).
export const dynamicParams = false;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const content = contentMap[slug];
  if (!content) {
    return { title: "Legal" };
  }
  return {
    title: content.title,
    description: content.description,
    alternates: { canonical: `/legal/${slug}` },
  };
}

export default async function LegalPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  const content = contentMap[slug];
  if (!content) {
    notFound();
  }

  return (
    <>
      <Navbar />
      <main className="pt-24 max-w-3xl mx-auto px-4 pb-16">
        <h1 className="font-cinzel text-4xl font-bold text-gradient mb-8">
          {content.title}
        </h1>
        <div className="text-gray-300 space-y-4">
          {content.body.map((paragraph, idx) => (
            <p key={idx} className="leading-relaxed">
              {paragraph}
            </p>
          ))}
        </div>
      </main>
      <Footer />
    </>
  );
}
