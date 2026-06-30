import React from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata = {
  title: "Privacy Policy | PuranGPT",
  description: "Privacy Policy for PuranGPT",
};

export default function PrivacyPage() {
  return (
    <div className="min-h-screen text-[#e5e2e1]" style={{ background: "#0e0e0e" }}>
      <div className="max-w-3xl mx-auto px-6 py-16">
        <Link href="/" className="inline-flex items-center gap-2 text-[#a38d7c] hover:text-[#e8b63f] transition-colors mb-8 text-sm" style={{ fontFamily: "var(--font-ui)" }}>
          <ArrowLeft className="w-4 h-4" />
          Back to Home
        </Link>
        
        <h1 className="text-3xl md:text-4xl font-bold mb-8 text-[#e8b63f]" style={{ fontFamily: "var(--font-display)" }}>
          Privacy Policy
        </h1>
        
        <div className="space-y-8 text-sm md:text-base leading-relaxed" style={{ fontFamily: "var(--font-body)" }}>
          <section>
            <p className="text-[#a38d7c] mb-4">Last Updated: June 18, 2026</p>
            <p>At PuranGPT, your privacy is critically important to us. This Privacy Policy outlines how we collect, use, and protect your information when you use our website and application.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>1. Information We Collect</h2>
            <ul className="list-disc pl-5 space-y-2 text-[#a38d7c]">
              <li><strong className="text-[#e5e2e1]">Account Information:</strong> When you register (e.g., via Google Auth or Email), we collect your name, email address, and profile picture.</li>
              <li><strong className="text-[#e5e2e1]">Chat Data:</strong> We store the conversations you have with our AI to provide conversation history and context.</li>
              <li><strong className="text-[#e5e2e1]">Payment Information:</strong> For paid subscriptions, payment processing is handled entirely by Razorpay. We do not store or process your credit card details on our servers.</li>
              <li><strong className="text-[#e5e2e1]">Usage Data:</strong> We collect basic analytics on how our service is accessed and used to improve performance.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>2. How We Use Your Information</h2>
            <p>We use the collected data to:</p>
            <ul className="list-disc pl-5 mt-2 space-y-1 text-[#a38d7c]">
              <li>Provide, operate, and maintain our application.</li>
              <li>Process transactions and manage subscriptions.</li>
              <li>Improve, personalize, and expand our AI responses.</li>
              <li>Communicate with you regarding updates, support, or security alerts.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>3. Data Security</h2>
            <p>We implement robust security measures to protect your personal information. Our databases are hosted securely on private servers, and authentication is handled via industry-standard protocols.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>4. Third-Party Services</h2>
            <p>We use trusted third-party services including Logto (Authentication) and Razorpay (Payments). These services have their own privacy policies governing the data they process on our behalf.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>5. Your Rights</h2>
            <p>You have the right to request access to, correction of, or deletion of your personal data. You can delete your account data directly from the Settings page or by contacting support.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>6. Contact Us</h2>
            <p>For any privacy-related inquiries, please contact us at <a href="mailto:support@purangpt.com" className="text-[#e8b63f] hover:underline">support@purangpt.com</a>.</p>
          </section>
        </div>
      </div>
    </div>
  );
}
