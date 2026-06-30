"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation, type Translations } from "@/lib/i18n";

export function FAQ() {
  const { language } = useLanguage();
  const [expanded, setExpanded] = useState<number | null>(0);

  const faqs: {
    categoryKey: keyof Translations;
    items: { qKey: keyof Translations; aKey: keyof Translations }[];
  }[] = [
    {
      categoryKey: "faq.cat1",
      items: [
        { qKey: "faq.q1", aKey: "faq.a1" },
        { qKey: "faq.q2", aKey: "faq.a2" },
        { qKey: "faq.q3", aKey: "faq.a3" },
      ],
    },
    {
      categoryKey: "faq.cat2",
      items: [
        { qKey: "faq.q4", aKey: "faq.a4" },
        { qKey: "faq.q5", aKey: "faq.a5" },
        { qKey: "faq.q6", aKey: "faq.a6" },
      ],
    },
    {
      categoryKey: "faq.cat3",
      items: [
        { qKey: "faq.q7", aKey: "faq.a7" },
        { qKey: "faq.q8", aKey: "faq.a8" },
        { qKey: "faq.q9", aKey: "faq.a9" },
      ],
    },
  ];

  const toggleExpand = (idx: number) => {
    setExpanded(expanded === idx ? null : idx);
  };

  let faqIndex = 0;

  return (
    <section id="faq" className="w-full py-24 px-4 sm:px-6 lg:px-8 bg-dark-900">
      <div className="max-w-3xl mx-auto">
        <motion.div
          className="text-center mb-16"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-100px" }}
        >
          <h2 className="text-4xl sm:text-5xl font-bold font-cinzel text-gradient mb-4">
            {getTranslation(language, "faq.title")}
          </h2>
          <p className="text-gray-300 text-lg">
            {getTranslation(language, "faq.subtitle")}
          </p>
        </motion.div>

        {/* FAQ Accordion */}
        <div className="space-y-4">
          {faqs.map((category) => (
            <div key={category.categoryKey} className="mb-8">
              <h3 className="text-lg font-semibold text-saffron mb-4 uppercase tracking-wide">
                {getTranslation(language, category.categoryKey)}
              </h3>

              <div className="space-y-3">
                {category.items.map((item) => {
                  const currentIdx = faqIndex++;
                  return (
                    <motion.div
                      key={currentIdx}
                      className="border border-gray-700 rounded-lg overflow-hidden hover:border-saffron/50 transition-colors"
                    >
                      <button
                        onClick={() => toggleExpand(currentIdx)}
                        className="w-full px-6 py-4 flex items-center justify-between hover:bg-dark-800 transition-colors text-left"
                      >
                        <span className="font-semibold text-white">{getTranslation(language, item.qKey)}</span>
                        <motion.div
                          animate={{ rotate: expanded === currentIdx ? 180 : 0 }}
                          transition={{ duration: 0.3 }}
                        >
                          <ChevronDown className="w-5 h-5 text-saffron" />
                        </motion.div>
                      </button>

                      <AnimatePresence>
                        {expanded === currentIdx && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.3 }}
                            className="border-t border-gray-700 bg-dark-800/50 px-6 py-4"
                          >
                            <p className="text-gray-300 leading-relaxed">{getTranslation(language, item.aKey)}</p>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </motion.div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {/* CTA */}
        <motion.div
          className="mt-16 text-center p-8 rounded-xl bg-gradient-to-r from-saffron/10 to-amber-500/10 border border-saffron/30"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
        >
          <p className="text-gray-300 mb-4">{getTranslation(language, "faq.cta")}</p>
          <button className="btn-primary">{getTranslation(language, "faq.cta_btn")}</button>
        </motion.div>
      </div>
    </section>
  );
}
