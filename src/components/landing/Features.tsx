"use client";

import { motion } from "framer-motion";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation, type Translations } from "@/lib/i18n";

// Sacred SVG symbols
function OmIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={className} fill="currentColor">
      <text x="50%" y="57%" dominantBaseline="middle" textAnchor="middle" fontSize="30" fontFamily="serif">ॐ</text>
    </svg>
  );
}
function TrishulIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 52" fill="none" className={className}>
      <rect x="18.5" y="28" width="3" height="22" rx="1.5" fill="currentColor" opacity="0.85"/>
      <path d="M20 7 Q12 13 13 27" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none"/>
      <path d="M20 7 Q28 13 27 27" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none"/>
      <path d="M20 4 L20 27" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" fill="none"/>
      <circle cx="13" cy="27" r="2" fill="currentColor"/>
      <circle cx="27" cy="27" r="2" fill="currentColor"/>
      <circle cx="20" cy="4" r="2.5" fill="currentColor"/>
      <rect x="12" y="29" width="16" height="2.5" rx="1.25" fill="currentColor" opacity="0.7"/>
    </svg>
  );
}
function SriChakraIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className}>
      <circle cx="20" cy="20" r="18" stroke="currentColor" strokeWidth="0.7" opacity="0.4"/>
      <polygon points="20,4 33,28 7,28" stroke="currentColor" strokeWidth="1.2" fill="none" opacity="0.8"/>
      <polygon points="20,36 7,12 33,12" stroke="currentColor" strokeWidth="1.2" fill="none" opacity="0.8"/>
      <circle cx="20" cy="20" r="2.5" fill="currentColor" opacity="0.9"/>
    </svg>
  );
}
function SuryaIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className}>
      <circle cx="20" cy="20" r="7" stroke="currentColor" strokeWidth="1.5" fill="none"/>
      {[0,45,90,135,180,225,270,315].map((angle, i) => (
        <line
          key={i}
          x1={20 + 10 * Math.cos((angle * Math.PI) / 180)}
          y1={20 + 10 * Math.sin((angle * Math.PI) / 180)}
          x2={20 + 16 * Math.cos((angle * Math.PI) / 180)}
          y2={20 + 16 * Math.sin((angle * Math.PI) / 180)}
          stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"
        />
      ))}
    </svg>
  );
}
function LotusIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className}>
      <ellipse cx="20" cy="28" rx="4" ry="10" stroke="currentColor" strokeWidth="1.2" fill="none" opacity="0.9"/>
      <ellipse cx="13" cy="25" rx="3.5" ry="9" transform="rotate(-25 13 25)" stroke="currentColor" strokeWidth="1.2" fill="none" opacity="0.7"/>
      <ellipse cx="27" cy="25" rx="3.5" ry="9" transform="rotate(25 27 25)" stroke="currentColor" strokeWidth="1.2" fill="none" opacity="0.7"/>
      <ellipse cx="8" cy="22" rx="3" ry="7.5" transform="rotate(-45 8 22)" stroke="currentColor" strokeWidth="1" fill="none" opacity="0.5"/>
      <ellipse cx="32" cy="22" rx="3" ry="7.5" transform="rotate(45 32 22)" stroke="currentColor" strokeWidth="1" fill="none" opacity="0.5"/>
      <line x1="20" y1="38" x2="20" y2="28" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}
function VajraIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className}>
      {/* Swastika as sacred geometry (auspicious Sanatana symbol) */}
      <rect x="18" y="8" width="4" height="24" rx="2" fill="currentColor" opacity="0.8"/>
      <rect x="8" y="18" width="24" height="4" rx="2" fill="currentColor" opacity="0.8"/>
      {/* Arms */}
      <rect x="22" y="8" width="6" height="4" rx="1" fill="currentColor" opacity="0.6"/>
      <rect x="22" y="28" width="6" height="4" rx="1" fill="currentColor" opacity="0.6"/>
      <rect x="8" y="12" width="4" height="6" rx="1" fill="currentColor" opacity="0.6"/>
      <rect x="28" y="22" width="4" height="6" rx="1" fill="currentColor" opacity="0.6"/>
    </svg>
  );
}
function SankhIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className}>
      <path d="M20 6 C10 6 5 13 5 20 C5 30 12 35 20 35 C25 35 28 31 28 27 C28 22 24 19 20 19 C16 19 13 22 14 26" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" fill="none"/>
      <path d="M14 26 C14 30 17 33 20 33" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
      <path d="M28 10 C32 12 35 16 35 20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" opacity="0.6"/>
    </svg>
  );
}
function YantraIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className}>
      <circle cx="20" cy="20" r="17" stroke="currentColor" strokeWidth="0.8" opacity="0.3"/>
      <circle cx="20" cy="20" r="13" stroke="currentColor" strokeWidth="0.8" opacity="0.4"/>
      <circle cx="20" cy="20" r="9" stroke="currentColor" strokeWidth="0.8" opacity="0.5"/>
      <polygon points="20,7 30,26 10,26" stroke="currentColor" strokeWidth="1.2" fill="none" opacity="0.8"/>
      <polygon points="20,33 10,14 30,14" stroke="currentColor" strokeWidth="1.2" fill="none" opacity="0.8"/>
      <circle cx="20" cy="20" r="2" fill="currentColor"/>
    </svg>
  );
}

interface Feature {
  // Precise icon type — NOT React.ElementType (which r3f's global JSX
  // augmentation collapses to `never` for className/strokeWidth). These are
  // custom SVG icon components; an SVG component type fits them exactly.
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  titleKey: keyof Translations;
  descKey: keyof Translations;
  color: string;
}

const features: Feature[] = [
  {
    icon: OmIcon,
    titleKey: "feat.f1.title",
    descKey: "feat.f1.desc",
    color: "from-orange-500/20 to-amber-500/20",
  },
  {
    icon: SriChakraIcon,
    titleKey: "feat.f2.title",
    descKey: "feat.f2.desc",
    color: "from-yellow-500/20 to-orange-500/20",
  },
  {
    icon: LotusIcon,
    titleKey: "feat.f3.title",
    descKey: "feat.f3.desc",
    color: "from-amber-500/20 to-yellow-500/20",
  },
  {
    icon: YantraIcon,
    titleKey: "feat.f4.title",
    descKey: "feat.f4.desc",
    color: "from-orange-500/20 to-red-500/20",
  },
  {
    icon: TrishulIcon,
    titleKey: "feat.f5.title",
    descKey: "feat.f5.desc",
    color: "from-yellow-400/20 to-orange-400/20",
  },
  {
    icon: SankhIcon,
    titleKey: "feat.f6.title",
    descKey: "feat.f6.desc",
    color: "from-orange-400/20 to-amber-400/20",
  },
  {
    icon: SuryaIcon,
    titleKey: "feat.f7.title",
    descKey: "feat.f7.desc",
    color: "from-amber-400/20 to-yellow-400/20",
  },
  {
    icon: VajraIcon,
    titleKey: "feat.f8.title",
    descKey: "feat.f8.desc",
    color: "from-orange-600/20 to-amber-600/20",
  },
];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.1, delayChildren: 0.2 } },
};
const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5 } },
};

export function Features() {
  const { language } = useLanguage();
  return (
    <section
      id="features"
      className="relative overflow-hidden bg-gradient-to-b from-[#0d0d0d] via-[#000000] to-[#0d0d0d] py-24 px-4 sm:px-6 lg:px-8"
    >
      {/* Sacred geometry watermarks */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-96 h-96 bg-[#a78bfa]/8 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 right-0 w-72 h-72 bg-[#c0392b]/6 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] opacity-[0.025] pointer-events-none">
        <SriChakraIcon className="w-full h-full text-[#a78bfa]" />
      </div>

      <div className="relative z-10 max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <div className="inline-flex items-center gap-2 mb-6 px-4 py-1.5 rounded-[4px] border border-[#353534] bg-[#141121]">
            <OmIcon className="w-4 h-4 text-[#a78bfa]" />
            <span className="text-xs uppercase tracking-widest text-[#a38d7c]">{getTranslation(language, "feat.badge")}</span>
          </div>
          <h2
            className="text-4xl sm:text-5xl font-bold mb-6"
            style={{ fontFamily: "var(--font-marcellus, serif)" }}
          >
            <span className="bg-gradient-to-r from-[#a5b4fc] via-[#a78bfa] to-[#a5b4fc] bg-clip-text text-transparent">
              {getTranslation(language, "feat.title_1")}
            </span>{" "}
            <span className="text-[#e5e2e1]">{getTranslation(language, "feat.title_2")}</span>
          </h2>
          <p className="text-[#a38d7c] text-lg max-w-2xl mx-auto leading-relaxed">
            {getTranslation(language, "feat.subtitle")}
          </p>
        </motion.div>

        {/* Features Grid */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8"
        >
          {features.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <motion.div
                key={index}
                variants={itemVariants}
                whileHover={{ y: -6, transition: { duration: 0.25 } }}
                className="group relative"
              >
                <div
                  className={`absolute inset-0 bg-gradient-to-br ${feature.color} rounded-[4px] opacity-60`}
                />
                <div className="relative bg-[#1a1a1a]/80 backdrop-blur-sm rounded-[4px] p-8 h-full border border-[#2a2a2a] group-hover:border-[#a78bfa]/30 transition-colors duration-300 flex flex-col">
                  {/* Icon */}
                  <div className="mb-6 inline-flex w-14 h-14 items-center justify-center rounded-[4px] bg-[#a78bfa]/10 border border-[#a78bfa]/20 group-hover:border-[#a78bfa]/50 transition-colors duration-300">
                    <Icon className="w-7 h-7 text-[#a78bfa]" />
                  </div>
                  <h3
                    className="text-lg font-semibold text-[#e5e2e1] mb-3 group-hover:text-[#a5b4fc] transition-colors duration-300"
                    style={{ fontFamily: "var(--font-marcellus, serif)" }}
                  >
                    {getTranslation(language, feature.titleKey)}
                  </h3>
                  <p className="text-[#a38d7c] text-sm leading-relaxed flex-grow group-hover:text-[#dbc2b0] transition-colors duration-300">
                    {getTranslation(language, feature.descKey)}
                  </p>
                  <motion.div
                    initial={{ scaleX: 0, originX: 0 }}
                    whileHover={{ scaleX: 1 }}
                    transition={{ duration: 0.3 }}
                    className="mt-6 h-px bg-gradient-to-r from-[#a78bfa] to-[#a5b4fc]"
                  />
                </div>
              </motion.div>
            );
          })}
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.4 }}
          className="text-center mt-16"
        >
          <p className="text-[#554336] text-sm">
            {getTranslation(language, "feat.footer_1")}{" "}
            <span className="text-[#a78bfa]">{getTranslation(language, "feat.footer_2")}</span>
          </p>
        </motion.div>
      </div>
    </section>
  );
}
