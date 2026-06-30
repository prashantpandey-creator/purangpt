"use client";

import { motion } from "framer-motion";
import {
  CheckCircle2,
  BookOpen,
  Lightbulb,
  Globe,
  BarChart3,
  Shield,
  Award,
  Users,
} from "lucide-react";
import { useState, useEffect } from "react";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation } from "@/lib/i18n";

interface StatProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  description: string;
}

interface ComparisonItem {
  feature: string;
  puranGPT: string;
  genericAI: string;
  icon: React.ReactNode;
}

const StatCounter = ({
  endValue,
  suffix,
  duration = 2,
}: {
  endValue: number;
  suffix: string;
  duration?: number;
}) => {
  const [count, setCount] = useState(0);

  useEffect(() => {
    let startTime: number;
    let animationFrameId: number;

    const animate = (currentTime: number) => {
      if (!startTime) startTime = currentTime;
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / (duration * 1000), 1);

      setCount(Math.floor(endValue * progress));

      if (progress < 1) {
        animationFrameId = requestAnimationFrame(animate);
      }
    };

    animationFrameId = requestAnimationFrame(animate);

    return () => cancelAnimationFrame(animationFrameId);
  }, [endValue, duration]);

  return (
    <span>
      {count}
      {suffix}
    </span>
  );
};

const StatCard: React.FC<StatProps> = ({
  icon,
  label,
  value,
  description,
}) => {
  const isPercentage = value.includes("%");
  const isNumber = /^\d+/.test(value);
  const numValue = isNumber
    ? parseInt(value.replace(/[^\d]/g, ""))
    : 0;
  const suffix = value.replace(/^\d+/, "");

  return (
    <motion.div
      className="group relative overflow-hidden rounded-lg border border-saffron/20 bg-gradient-to-br from-saffron/5 to-transparent p-6 sm:p-8 hover:border-saffron/40 transition-all duration-300"
      whileHover={{ y: -5 }}
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6 }}
      viewport={{ once: true, margin: "-100px" }}
    >
      <div className="absolute inset-0 bg-gradient-to-br from-saffron/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />

      <div className="relative z-10 space-y-4">
        <div className="w-12 h-12 rounded-lg bg-saffron/10 flex items-center justify-center">
          <div className="text-saffron">{icon}</div>
        </div>

        <div className="space-y-2">
          <div className="text-3xl sm:text-4xl font-bold text-white font-cinzel">
            {isNumber ? (
              <motion.div
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                viewport={{ once: true, margin: "-100px" }}
              >
                <StatCounter
                  endValue={numValue}
                  suffix={suffix}
                  duration={2}
                />
              </motion.div>
            ) : (
              value
            )}
          </div>
          <p className="text-sm font-medium text-saffron">{label}</p>
        </div>

        <p className="text-sm text-gray-400 leading-relaxed">{description}</p>
      </div>
    </motion.div>
  );
};

const ComparisonRow: React.FC<ComparisonItem> = ({
  feature,
  puranGPT,
  genericAI,
  icon,
}) => {
  return (
    <motion.div
      className="group border-b border-saffron/10 last:border-b-0"
      initial={{ opacity: 0, x: -20 }}
      whileInView={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.5 }}
      viewport={{ once: true, margin: "-50px" }}
    >
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6 py-6 px-4 sm:px-6 hover:bg-saffron/5 transition-colors duration-300 rounded">
        <div className="flex items-start gap-3 sm:col-span-1">
          <div className="w-5 h-5 mt-1 text-saffron flex-shrink-0">{icon}</div>
          <span className="font-medium text-gray-200 text-sm sm:text-base">
            {feature}
          </span>
        </div>

        <div className="sm:col-span-1 sm:text-center">
          <div className="flex items-start gap-2 sm:flex-col">
            <CheckCircle2 className="w-4 h-4 text-saffron flex-shrink-0 sm:hidden" />
            <span className="text-green-400 font-medium text-sm sm:text-base">
              {puranGPT}
            </span>
          </div>
        </div>

        <div className="sm:col-span-1 sm:text-center">
          <div className="flex items-start gap-2 sm:flex-col">
            <div className="w-4 h-4 border-2 border-red-500/50 rounded-full flex-shrink-0 sm:hidden" />
            <span className="text-gray-500 text-sm sm:text-base">{genericAI}</span>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export function WhyChooseUs() {
  const { language } = useLanguage();

  const comparisonData: ComparisonItem[] = [
    {
      feature: getTranslation(language, "why.cmp1.feature"),
      puranGPT: getTranslation(language, "why.cmp1.purangpt"),
      genericAI: getTranslation(language, "why.cmp1.generic"),
      icon: <BookOpen className="w-5 h-5" />,
    },
    {
      feature: getTranslation(language, "why.cmp2.feature"),
      puranGPT: getTranslation(language, "why.cmp2.purangpt"),
      genericAI: getTranslation(language, "why.cmp2.generic"),
      icon: <Globe className="w-5 h-5" />,
    },
    {
      feature: getTranslation(language, "why.cmp3.feature"),
      puranGPT: getTranslation(language, "why.cmp3.purangpt"),
      genericAI: getTranslation(language, "why.cmp3.generic"),
      icon: <Users className="w-5 h-5" />,
    },
    {
      feature: getTranslation(language, "why.cmp4.feature"),
      puranGPT: getTranslation(language, "why.cmp4.purangpt"),
      genericAI: getTranslation(language, "why.cmp4.generic"),
      icon: <Award className="w-5 h-5" />,
    },
  ];

  const statsData: StatProps[] = [
    {
      icon: <BookOpen className="w-6 h-6" />,
      label: getTranslation(language, "why.stat1.label"),
      value: "30+",
      description: getTranslation(language, "why.stat1.desc"),
    },
    {
      icon: <BarChart3 className="w-6 h-6" />,
      label: getTranslation(language, "why.stat2.label"),
      value: "100000+",
      description: getTranslation(language, "why.stat2.desc"),
    },
    {
      icon: <Shield className="w-6 h-6" />,
      label: getTranslation(language, "why.stat3.label"),
      value: "92%",
      description: getTranslation(language, "why.stat3.desc"),
    },
    {
      icon: <Lightbulb className="w-6 h-6" />,
      label: getTranslation(language, "why.stat4.label"),
      value: "0%",
      description: getTranslation(language, "why.stat4.desc"),
    },
  ];

  const authorityMarkers = [
    getTranslation(language, "why.marker1"),
    getTranslation(language, "why.marker2"),
    getTranslation(language, "why.marker3"),
    getTranslation(language, "why.marker4"),
  ];

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
        delayChildren: 0.2,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.6 },
    },
  };

  return (
    <section className="relative w-full py-16 sm:py-24 lg:py-32 overflow-hidden bg-dark-900 px-4 sm:px-6 lg:px-8">
      {/* Background decoration */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-20 right-10 w-72 h-72 bg-saffron/5 rounded-full blur-3xl animate-pulse" />
        <div className="absolute bottom-40 -left-20 w-96 h-96 bg-amber-500/3 rounded-full blur-3xl animate-pulse" />
      </div>

      <div className="relative z-10 max-w-6xl mx-auto">
        {/* Header */}
        <motion.div
          className="text-center space-y-4 mb-16 sm:mb-20"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
        >
          <motion.div variants={itemVariants}>
            <span className="inline-block px-4 py-2 rounded-full border border-saffron/30 bg-saffron/5 backdrop-blur-md text-sm font-medium text-saffron">
              {getTranslation(language, "why.badge")}
            </span>
          </motion.div>

          <motion.h2
            variants={itemVariants}
            className="text-4xl sm:text-5xl md:text-6xl font-bold font-cinzel leading-tight"
          >
            <span className="text-gradient">{getTranslation(language, "why.title_1")}</span>
            <br />
            <span className="text-gray-400">{getTranslation(language, "why.title_2")}</span>
          </motion.h2>

          <motion.p
            variants={itemVariants}
            className="text-lg text-gray-300 max-w-2xl mx-auto leading-relaxed"
          >
            {getTranslation(language, "why.subtitle")}
          </motion.p>
        </motion.div>

        {/* Stats Grid */}
        <motion.div
          className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 mb-16 sm:mb-20"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
        >
          {statsData.map((stat) => (
            <motion.div key={stat.label} variants={itemVariants}>
              <StatCard {...stat} />
            </motion.div>
          ))}
        </motion.div>

        {/* Authority Markers */}
        <motion.div
          className="flex flex-wrap gap-3 sm:gap-4 justify-center mb-16 sm:mb-20"
          variants={containerVariants}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-100px" }}
        >
          {authorityMarkers.map((marker) => (
            <motion.div
              key={marker}
              variants={itemVariants}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-saffron/20 bg-saffron/5 backdrop-blur-sm hover:border-saffron/40 hover:bg-saffron/10 transition-all duration-300"
            >
              <CheckCircle2 className="w-4 h-4 text-saffron" />
              <span className="text-sm font-medium text-gray-200">{marker}</span>
            </motion.div>
          ))}
        </motion.div>

        {/* Comparison Section */}
        <motion.div
          className="space-y-4 sm:space-y-6"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          viewport={{ once: true, margin: "-100px" }}
        >
          <div className="mb-8 sm:mb-10">
            <h3 className="text-2xl sm:text-3xl font-bold font-cinzel text-white mb-2">
              {getTranslation(language, "why.comparison_title")}
            </h3>
            <p className="text-gray-400">
              {getTranslation(language, "why.comparison_subtitle")}
            </p>
          </div>

          {/* Comparison Table Header */}
          <div className="hidden sm:grid sm:grid-cols-3 gap-6 px-6 py-4 rounded-t-lg border border-saffron/20 bg-saffron/5 border-b-0">
            <div className="font-semibold text-gray-300">{getTranslation(language, "why.col_feature")}</div>
            <div className="text-center font-semibold text-saffron">{getTranslation(language, "why.col_purangpt")}</div>
            <div className="text-center font-semibold text-gray-500">
              {getTranslation(language, "why.col_generic")}
            </div>
          </div>

          {/* Comparison Rows */}
          <motion.div
            className="border border-saffron/20 rounded-lg sm:rounded-b-lg overflow-hidden bg-gradient-to-b from-saffron/5 to-transparent"
            variants={containerVariants}
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
          >
            {comparisonData.map((item, index) => (
              <motion.div key={index} variants={itemVariants}>
                <ComparisonRow {...item} />
              </motion.div>
            ))}
          </motion.div>
        </motion.div>

        {/* CTA */}
        <motion.div
          className="text-center mt-16 sm:mt-20"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          viewport={{ once: true, margin: "-100px" }}
        >
          <button className="btn-primary">
            {getTranslation(language, "why.cta")}
          </button>
          <p className="text-sm text-gray-500 mt-4">
            {getTranslation(language, "why.cta_sub")}
          </p>
        </motion.div>
      </div>
    </section>
  );
}
