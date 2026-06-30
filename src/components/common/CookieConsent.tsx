"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { X, Cookie } from "lucide-react";

export function CookieConsent() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    const consent = localStorage.getItem("cookie_consent");
    if (!consent) {
      // Small delay so it doesn't pop up instantly on load
      const timer = setTimeout(() => setShow(true), 1500);
      return () => clearTimeout(timer);
    }
  }, []);

  const handleAccept = () => {
    localStorage.setItem("cookie_consent", "accepted");
    setShow(false);
  };

  const handleReject = () => {
    localStorage.setItem("cookie_consent", "rejected");
    setShow(false);
  };

  return (
    <AnimatePresence>
      {show && (
        <motion.div
          initial={{ y: 100, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 100, opacity: 0 }}
          className="fixed bottom-4 left-4 right-4 md:left-auto md:right-8 z-[100] max-w-sm w-full bg-dark-800 border border-saffron/20 rounded-xl shadow-2xl overflow-hidden"
        >
          <div className="absolute inset-0 bg-gradient-to-br from-saffron/5 to-transparent pointer-events-none" />
          <div className="p-5 relative z-10">
            <div className="flex justify-between items-start mb-3">
              <div className="flex items-center gap-2">
                <Cookie className="w-5 h-5 text-saffron" />
                <h3 className="font-semibold text-gray-100">Privacy & Cookies</h3>
              </div>
              <button
                onClick={() => setShow(false)}
                className="text-gray-400 hover:text-white transition-colors"
                aria-label="Close"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            
            <p className="text-sm text-gray-300 leading-relaxed mb-4">
              We use cookies to improve your experience, remember your preferences, and analyze our traffic. Read our{" "}
              <Link href="/privacy" className="text-saffron hover:underline">
                Privacy Policy
              </Link>{" "}
              and{" "}
              <Link href="/terms" className="text-saffron hover:underline">
                Terms
              </Link>
              .
            </p>

            <div className="flex flex-col sm:flex-row gap-2">
              <button
                onClick={handleAccept}
                className="btn-primary py-2 px-4 text-xs flex-1"
              >
                Accept All
              </button>
              <button
                onClick={handleReject}
                className="btn-secondary py-2 px-4 text-xs flex-1 border-gray-600 text-gray-300 hover:bg-gray-700 hover:text-white"
              >
                Reject Non-Essential
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
