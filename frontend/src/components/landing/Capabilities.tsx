'use client';

import { motion } from 'framer-motion';
import {
  BookMarked,
  Flame,
  FileText,
  Languages,
  ShieldCheck,
  History,
  ArrowRight,
} from 'lucide-react';
import { useLanguage } from '@/context/LanguageContext';
import { getTranslation, type Translations } from '@/lib/i18n';

interface Capability {
  // Precise icon type — NOT React.ElementType. The latter is the union of every
  // possible JSX tag, which (since r3f augments the global JSX namespace with
  // three elements that lack className/strokeWidth) collapses those props to
  // `never`. An SVG component type carries exactly the props we pass.
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  titleKey: keyof Translations;
  subtitleKey: keyof Translations;
  descKey: keyof Translations;
  useCaseKey: keyof Translations;
  color: {
    from: string;
    to: string;
    accent: string;
    lightBg: string;
  };
  mockupKey: keyof Translations;
}

const capabilities: Capability[] = [
  {
    icon: BookMarked,
    titleKey: 'cap.c1.title',
    subtitleKey: 'cap.c1.subtitle',
    descKey: 'cap.c1.desc',
    useCaseKey: 'cap.c1.usecase',
    color: {
      from: 'from-orange-500',
      to: 'to-amber-500',
      accent: 'text-orange-300',
      lightBg: 'from-orange-500/20 to-amber-500/20',
    },
    mockupKey: 'cap.c1.mockup',
  },
  {
    icon: Flame,
    titleKey: 'cap.c2.title',
    subtitleKey: 'cap.c2.subtitle',
    descKey: 'cap.c2.desc',
    useCaseKey: 'cap.c2.usecase',
    color: {
      from: 'from-yellow-500',
      to: 'to-orange-400',
      accent: 'text-yellow-300',
      lightBg: 'from-yellow-500/20 to-orange-400/20',
    },
    mockupKey: 'cap.c2.mockup',
  },
  {
    icon: FileText,
    titleKey: 'cap.c3.title',
    subtitleKey: 'cap.c3.subtitle',
    descKey: 'cap.c3.desc',
    useCaseKey: 'cap.c3.usecase',
    color: {
      from: 'from-red-500',
      to: 'to-orange-500',
      accent: 'text-red-300',
      lightBg: 'from-red-500/20 to-orange-500/20',
    },
    mockupKey: 'cap.c3.mockup',
  },
  {
    icon: Languages,
    titleKey: 'cap.c4.title',
    subtitleKey: 'cap.c4.subtitle',
    descKey: 'cap.c4.desc',
    useCaseKey: 'cap.c4.usecase',
    color: {
      from: 'from-emerald-500',
      to: 'to-teal-500',
      accent: 'text-emerald-300',
      lightBg: 'from-emerald-500/20 to-teal-500/20',
    },
    mockupKey: 'cap.c4.mockup',
  },
  {
    icon: ShieldCheck,
    titleKey: 'cap.c5.title',
    subtitleKey: 'cap.c5.subtitle',
    descKey: 'cap.c5.desc',
    useCaseKey: 'cap.c5.usecase',
    color: {
      from: 'from-violet-500',
      to: 'to-purple-500',
      accent: 'text-violet-300',
      lightBg: 'from-violet-500/20 to-purple-500/20',
    },
    mockupKey: 'cap.c5.mockup',
  },
  {
    icon: History,
    titleKey: 'cap.c6.title',
    subtitleKey: 'cap.c6.subtitle',
    descKey: 'cap.c6.desc',
    useCaseKey: 'cap.c6.usecase',
    color: {
      from: 'from-cyan-500',
      to: 'to-blue-500',
      accent: 'text-cyan-300',
      lightBg: 'from-cyan-500/20 to-blue-500/20',
    },
    mockupKey: 'cap.c6.mockup',
  },
];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.12,
      delayChildren: 0.3,
    },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 30 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.6,
    },
  },
};

const cardHoverVariants = {
  rest: {
    y: 0,
    boxShadow: '0 10px 30px rgba(0, 0, 0, 0.4)',
  },
  hover: {
    y: -12,
    boxShadow: '0 30px 60px rgba(232,182,63, 0.15)',
    transition: {
      duration: 0.4,
    },
  },
};

const iconVariants = {
  rest: { scale: 1, rotate: 0 },
  hover: {
    scale: 1.2,
    rotate: -5,
    transition: {
      duration: 0.4,
    },
  },
};

const glowVariants = {
  rest: {
    boxShadow: 'inset 0 0 0 1px rgba(232,182,63, 0.2)',
  },
  hover: {
    boxShadow: 'inset 0 0 0 2px rgba(232,182,63, 0.5), 0 0 30px rgba(232,182,63, 0.25)',
    transition: {
      duration: 0.4,
    },
  },
};

const mockupVariants = {
  rest: { opacity: 0.6 },
  hover: {
    opacity: 1,
    transition: {
      duration: 0.4,
    },
  },
};

export function Capabilities() {
  const { language } = useLanguage();
  return (
    <section id="capabilities" className="relative overflow-hidden bg-gradient-to-b from-[#0a0a0a] via-[#121212] to-[#0a0a0a] py-28 px-4 sm:px-6 lg:px-8">
      {/* Decorative background elements */}
      <div className="absolute top-20 left-1/4 -translate-x-1/2 w-96 h-96 bg-amber-600/8 rounded-full blur-3xl" />
      <div className="absolute bottom-40 right-1/4 w-80 h-80 bg-orange-600/8 rounded-full blur-3xl" />
      <div className="absolute top-1/2 right-10 w-72 h-72 bg-yellow-600/5 rounded-full blur-3xl" />

      <div className="relative z-10 max-w-7xl mx-auto">
        {/* Section Header */}
        <motion.div
          initial={{ opacity: 0, y: -30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.7 }}
          className="text-center mb-20"
        >
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            transition={{ delay: 0.2, duration: 0.5 }}
            className="inline-block mb-4"
          >
            <span className="px-4 py-2 rounded-full bg-gradient-to-r from-amber-500/20 to-orange-500/20 border border-amber-400/30 text-amber-300 text-sm font-semibold">
              {getTranslation(language, "cap.badge")}
            </span>
          </motion.div>

          <h2 className="text-5xl sm:text-6xl font-bold mb-6 mt-6">
            <span className="bg-gradient-to-r from-amber-300 via-orange-300 to-amber-200 bg-clip-text text-transparent">
              {getTranslation(language, "cap.title_1")}
            </span>
            <span className="text-gray-300"> {getTranslation(language, "cap.title_2")}</span>
          </h2>

          <p className="text-gray-400 text-lg max-w-3xl mx-auto leading-relaxed">
            {getTranslation(language, "cap.subtitle")}
          </p>
        </motion.div>

        {/* Capabilities Grid */}
        <motion.div
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: '-100px' }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8"
        >
          {capabilities.map((capability, index) => {
            const Icon = capability.icon;
            return (
              <motion.div
                key={index}
                variants={itemVariants}
                whileHover="hover"
                initial="rest"
                animate="rest"
              >
                <motion.div
                  variants={cardHoverVariants}
                  className="h-full relative group"
                >
                  {/* Card Background Gradient */}
                  <motion.div
                    variants={glowVariants}
                    className={`absolute inset-0 bg-gradient-to-br ${capability.color.lightBg} rounded-2xl pointer-events-none`}
                  />

                  {/* Main Card */}
                  <div className="relative bg-gradient-to-br from-gray-900/85 to-gray-950/85 backdrop-blur-lg rounded-2xl p-8 h-full border border-gray-800/50 flex flex-col overflow-hidden">
                    {/* Accent top line */}
                    <div
                      className={`absolute top-0 left-0 right-0 h-1 bg-gradient-to-r ${capability.color.from} ${capability.color.to}`}
                    />

                    {/* Icon Container */}
                    <motion.div
                      variants={iconVariants}
                      className={`mb-6 inline-flex w-16 h-16 items-center justify-center rounded-xl bg-gradient-to-br ${capability.color.from} ${capability.color.to} bg-opacity-20 backdrop-blur-md border ${capability.color.accent} border-opacity-40 group-hover:border-opacity-70 transition-all duration-300 shadow-lg`}
                    >
                      <Icon className={`w-8 h-8 ${capability.color.accent}`} strokeWidth={1.5} />
                    </motion.div>

                    {/* Title and Subtitle */}
                    <div className="mb-4">
                      <h3 className="text-2xl font-bold text-white mb-1 group-hover:text-amber-100 transition-colors duration-300">
                        {getTranslation(language, capability.titleKey)}
                      </h3>
                      <p
                        className={`text-sm font-semibold ${capability.color.accent} opacity-80 group-hover:opacity-100 transition-opacity duration-300`}
                      >
                        {getTranslation(language, capability.subtitleKey)}
                      </p>
                    </div>

                    {/* Description */}
                    <p className="text-gray-400 text-sm leading-relaxed mb-4 group-hover:text-gray-300 transition-colors duration-300">
                      {getTranslation(language, capability.descKey)}
                    </p>

                    {/* Use Case Badge */}
                    <div className="mb-6 p-3 rounded-lg bg-gray-800/40 border border-gray-700/50">
                      <p className="text-xs text-gray-300 font-medium leading-relaxed">
                        <span className="text-amber-300 font-bold">{getTranslation(language, "cap.use_case")}</span>
                        {getTranslation(language, capability.useCaseKey)}
                      </p>
                    </div>

                    {/* Mockup Preview */}
                    <motion.div
                      variants={mockupVariants}
                      className="mb-6 p-4 rounded-lg bg-black/40 border border-gray-700/30 group-hover:border-gray-600/60 transition-colors duration-300"
                    >
                      <div className="flex items-start gap-2">
                        <div className={`${capability.color.accent} text-lg flex-shrink-0 mt-0.5`}>
                          ▪
                        </div>
                        <p className="text-xs text-gray-400 group-hover:text-gray-300 transition-colors duration-300 leading-relaxed">
                          {getTranslation(language, capability.mockupKey)}
                        </p>
                      </div>
                    </motion.div>

                    {/* Learn More Link */}
                    <div className="mt-auto pt-4 border-t border-gray-800/50 flex items-center justify-between group/link">
                      <span className="text-xs font-semibold text-amber-400 opacity-0 group-hover/link:opacity-100 transition-opacity duration-300">
                        {getTranslation(language, "cap.explore")}
                      </span>
                      <motion.div
                        initial={{ x: 0 }}
                        whileHover={{ x: 4 }}
                        transition={{ duration: 0.3 }}
                      >
                        <ArrowRight className="w-4 h-4 text-gray-600 group-hover/link:text-amber-300 transition-colors duration-300" />
                      </motion.div>
                    </div>
                  </div>
                </motion.div>
              </motion.div>
            );
          })}
        </motion.div>

        {/* Info Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.5 }}
          className="mt-20 max-w-4xl mx-auto"
        >
          <div className="rounded-2xl border border-amber-400/20 bg-gradient-to-r from-amber-500/10 to-orange-500/10 backdrop-blur-md p-8 sm:p-12">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0">
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-amber-400/20 border border-amber-300/40">
                  <span className="text-xl">💡</span>
                </div>
              </div>
              <div>
                <h3 className="text-lg font-bold text-amber-100 mb-2">{getTranslation(language, "cap.info.title")}</h3>
                <p className="text-gray-300 leading-relaxed">
                  {getTranslation(language, "cap.info.desc")}
                </p>
              </div>
            </div>
          </div>
        </motion.div>

        {/* CTA Section */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.6 }}
          className="text-center mt-16"
        >
          <p className="text-gray-500 text-sm">
            {getTranslation(language, "cap.footer_1")}{' '}
            <span className="text-amber-300 font-semibold">{getTranslation(language, "cap.footer_2")}</span> and{' '}
            <span className="text-amber-300 font-semibold">{getTranslation(language, "cap.footer_3")}</span>.
          </p>
        </motion.div>
      </div>
    </section>
  );
}
