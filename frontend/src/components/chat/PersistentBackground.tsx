"use client";

import dynamic from "next/dynamic";

const ThreeBackground = dynamic(
  () => import("./ThreeBackground").then((m) => m.default),
  { ssr: false }
);

export default function PersistentBackground() {
  return <ThreeBackground phase="resting" />;
}
