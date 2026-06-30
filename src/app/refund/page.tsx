import React from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata = {
  title: "Refund & Cancellation Policy | PuranGPT",
  description: "Refund and Cancellation Policy for PuranGPT",
};

export default function RefundPage() {
  return (
    <div className="min-h-screen text-[#e5e2e1]" style={{ background: "#0e0e0e" }}>
      <div className="max-w-3xl mx-auto px-6 py-16">
        <Link href="/" className="inline-flex items-center gap-2 text-[#a38d7c] hover:text-[#e8b63f] transition-colors mb-8 text-sm" style={{ fontFamily: "var(--font-ui)" }}>
          <ArrowLeft className="w-4 h-4" />
          Back to Home
        </Link>
        
        <h1 className="text-3xl md:text-4xl font-bold mb-8 text-[#e8b63f]" style={{ fontFamily: "var(--font-display)" }}>
          Refund &amp; Cancellation Policy
        </h1>
        
        <div className="space-y-8 text-sm md:text-base leading-relaxed" style={{ fontFamily: "var(--font-body)" }}>
          <section>
            <p className="text-[#a38d7c] mb-4">Last Updated: June 18, 2026</p>
            <p>Thank you for subscribing to PuranGPT Pro. We want to ensure a transparent and fair experience regarding your subscription billing.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>1. Subscription Cancellations</h2>
            <p>You can cancel your subscription at any time through the Settings page or by contacting our support team. When you cancel:</p>
            <ul className="list-disc pl-5 mt-2 space-y-1 text-[#a38d7c]">
              <li>Your cancellation will take effect at the end of your current paid billing cycle.</li>
              <li>You will not be charged again moving forward.</li>
              <li>You will retain full access to Pro features until your paid period ends.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>2. Refund Eligibility</h2>
            <p>Due to the nature of digital API-based services and the immediate compute costs incurred when you use PuranGPT Pro, <strong>we generally do not offer refunds for partial subscription periods.</strong></p>
            <br />
            <p>However, we will issue a full refund under the following exceptional circumstances:</p>
            <ul className="list-disc pl-5 mt-2 space-y-1 text-[#a38d7c]">
              <li>You were charged in error due to a technical glitch.</li>
              <li>You request a refund within <strong>48 hours</strong> of your initial purchase AND have not heavily utilized the Pro capabilities (e.g., Deep Research).</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>3. How to Request a Refund</h2>
            <p>To request a refund under the eligible criteria, please email us directly from your registered email address with your order details.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>4. Processing Time</h2>
            <p>Approved refunds are processed through Razorpay and generally take 5-7 business days to reflect in your original payment method, depending on your bank.</p>
          </section>

          <section>
            <h2 className="text-xl font-semibold mb-3 text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)" }}>5. Contact</h2>
            <p>For billing support or cancellation requests, contact <a href="mailto:support@purangpt.com" className="text-[#e8b63f] hover:underline">support@purangpt.com</a>.</p>
          </section>
        </div>
      </div>
    </div>
  );
}
