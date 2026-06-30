import { AboutContent } from "./AboutContent";

export const metadata = {
  title: "About",
  description:
    "Why PuranGPT grounds every answer in scripture — covering the 18 Mahāpurāṇas, Mahābhārata, 108 Upaniṣads, and Yoga texts with exact, citable verses.",
  alternates: { canonical: "/about" },
  openGraph: {
    title: "About PuranGPT",
    description:
      "Why PuranGPT grounds every answer in scripture — real verses, real citations across the 18 Mahāpurāṇas, Mahābhārata, Upaniṣads, and Yoga texts.",
    url: "/about",
    type: "website",
  },
};

export default function AboutPage() {
  return <AboutContent />;
}
