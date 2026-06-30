import React from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata = {
  title: "Terms of Service | PuranGPT",
  description: "Terms of Service for PuranGPT",
};

export default function TermsPage() {
  return (
    <div className="min-h-screen text-[#e5e2e1]" style={{ background: "#0e0e0e" }}>
      <div className="max-w-3xl mx-auto px-6 py-16">
        <Link href="/" className="inline-flex items-center gap-2 text-[#a38d7c] hover:text-[#e8b63f] transition-colors mb-8 text-sm" style={{ fontFamily: "var(--font-ui)" }}>
          <ArrowLeft className="w-4 h-4" />
          Back to Home
        </Link>
        
        <h1 className="text-3xl md:text-4xl font-bold mb-8 text-[#e8b63f]" style={{ fontFamily: "var(--font-display)" }}>
          Terms of Service
        </h1>
        
        <div className="space-y-8 text-sm md:text-base leading-relaxed" style={{ fontFamily: "var(--font-body)" }}>
          <section>
            <p className="text-[#a38d7c] mb-4">Last Updated: June 18, 2026</p>
            <p>Welcome to PuranGPT. By accessing or using our website and application (purangpt.com), you agree to be bound by these Terms of Service. Please read them carefully.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>1. Acceptance of Terms</h2>
            <p>By registering for an account or using our services, you confirm that you accept these Terms of Service and agree to comply with them. If you do not agree to these terms, you must not use our services.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>2. Description of Service</h2>
            <p>PuranGPT provides AI-powered research and conversational interfaces accessing ancient Vedic texts. We offer both free access and paid subscription tiers (e.g., PuranGPT Pro) with enhanced capabilities and limits.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>3. Subscription and Billing</h2>
            <p>Paid subscriptions are billed on a recurring basis (monthly or annually) according to the selected plan. You must provide a valid payment method. By subscribing, you authorize us (via our payment processor, Razorpay) to charge your payment method on a recurring basis until cancellation.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>4. Cancellation Policy</h2>
            <p>You may cancel your subscription at any time. Cancellation takes effect at the end of your current billing cycle. You will retain access to paid features until that cycle concludes. See our Refund Policy for information on refunds.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>5. User Accounts</h2>
            <p>You are responsible for maintaining the confidentiality of your account credentials and for all activities that occur under your account. You must notify us immediately of any unauthorized use of your account.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>6. Limitation of Liability</h2>
            <p>PuranGPT is provided "as is" without any warranties. The AI-generated responses regarding Vedic literature are for educational and informational purposes only. We are not liable for any direct, indirect, incidental, or consequential damages resulting from your use of the service.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>7. Contact Us</h2>
            <p>If you have any questions about these Terms, please contact us at <a href="mailto:support@purangpt.com" className="text-[#e8b63f] hover:underline">support@purangpt.com</a>.</p>
          </section>
        </div>
      </div>
    </div>
  );
}
