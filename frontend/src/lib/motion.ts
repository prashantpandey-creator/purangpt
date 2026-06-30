import type { Transition } from "framer-motion";

// Expo-out glide — the "iOS feel" curve.
export const EASE_OUT_SOFT = [0.22, 1, 0.36, 1] as const;
// Material standard ease — good for elements that enter and exit.
export const EASE_STD = [0.4, 0, 0.2, 1] as const;
// Gravity-in — accelerates into the core. Used for the consume flight.
export const EASE_CONSUME = [0.4, 0, 1, 1] as const;

export const transitionSoft: Transition = {
  duration: 0.32,
  ease: EASE_OUT_SOFT,
};

export const springSoft: Transition = {
  type: "spring",
  stiffness: 300,
  damping: 30,
};

export const tap = { scale: 0.97 } as const;
