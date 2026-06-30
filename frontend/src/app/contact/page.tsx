import React from "react";
import Link from "next/link";
import { ArrowLeft, Mail, MapPin } from "lucide-react";

export const metadata = {
  title: "Contact Us | PuranGPT",
  description: "Get in touch with the PuranGPT team",
};

export default function ContactPage() {
  return (
    <div className="min-h-screen text-[#e5e2e1]" style={{ background: "#0e0e0e" }}>
      <div className="max-w-3xl mx-auto px-6 py-16">
        <Link href="/" className="inline-flex items-center gap-2 text-[#a38d7c] hover:text-[#e8b63f] transition-colors mb-8 text-sm" style={{ fontFamily: "var(--font-ui)" }}>
          <ArrowLeft className="w-4 h-4" />
          Back to Home
        </Link>
        
        <h1 className="text-3xl md:text-4xl font-bold mb-4 text-[#e8b63f]" style={{ fontFamily: "var(--font-display)" }}>
          Contact Us
        </h1>
        <p className="text-[#a38d7c] mb-12 text-sm md:text-base" style={{ fontFamily: "var(--font-body)" }}>
          Have a question about PuranGPT, need help with your subscription, or want to report an issue? We're here to help.
        </p>
        
        <div className="grid gap-8 md:grid-cols-2">
          
          <div className="rounded-2xl border border-white/10 p-6 space-y-4" style={{ background: "rgba(28,27,27,0.8)" }}>
            <div className="w-10 h-10 rounded-full bg-[#e8b63f]/15 flex items-center justify-center text-[#e8b63f]">
              <Mail className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-semibold text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>Email Support</h2>
            <p className="text-sm text-[#a38d7c]" style={{ fontFamily: "var(--font-body)" }}>
              For general inquiries, technical support, and billing assistance, please email us. We typically respond within 24 hours.
            </p>
            <a href="mailto:support@purangpt.com" className="inline-block mt-2 text-[#e8b63f] font-medium hover:underline" style={{ fontFamily: "var(--font-ui)" }}>
              support@purangpt.com
            </a>
          </div>

          <div className="rounded-2xl border border-white/10 p-6 space-y-4" style={{ background: "rgba(28,27,27,0.8)" }}>
            <div className="w-10 h-10 rounded-full bg-[#e8b63f]/15 flex items-center justify-center text-[#e8b63f]">
              <MapPin className="w-5 h-5" />
            </div>
            <h2 className="text-lg font-semibold text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>Operational Address</h2>
            <p className="text-sm text-[#a38d7c]" style={{ fontFamily: "var(--font-body)" }}>
              PuranGPT operates globally, but you can reach our administrative headquarters at:
            </p>
            <address className="text-sm text-[#a38d7c] not-italic leading-relaxed">
              New Delhi, India<br />
              (Online First Organization)
            </address>
          </div>

        </div>

      </div>
    </div>
  );
}
