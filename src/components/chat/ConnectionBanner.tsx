"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { WifiOff } from "lucide-react";

/**
 * Slim banner that drops in when the browser goes offline, so the user
 * understands why streaming may stall. Auto-dismisses when the connection
 * returns. Purely client-side via the online/offline events.
 */
export function ConnectionBanner() {
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    // Initialise from current state (navigator.onLine is reliable for "offline").
    setOffline(typeof navigator !== "undefined" && navigator.onLine === false);
    const goOffline = () => setOffline(true);
    const goOnline = () => setOffline(false);
    window.addEventListener("offline", goOffline);
    window.addEventListener("online", goOnline);
    return () => {
      window.removeEventListener("offline", goOffline);
      window.removeEventListener("online", goOnline);
    };
  }, []);

  return (
    <AnimatePresence>
      {offline && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.22 }}
          className="net-banner flex w-full items-center justify-center gap-2 overflow-hidden"
          role="status"
          aria-live="polite"
          style={{
            background: "rgba(232,182,63,0.12)",
            borderBottom: "1px solid rgba(232,182,63,0.3)",
            color: "#f0cd80",
          }}
        >
          <span className="flex items-center gap-2 py-1.5">
            <WifiOff className="h-3.5 w-3.5" />
            You&apos;re offline — responses are paused until the connection returns.
          </span>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
