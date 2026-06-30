"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Community Markdown renderer. Supports GFM (bold, italic, lists, quotes,
 * tables, strikethrough, autolinks) plus emoji (emoji are just unicode).
 * Raw HTML is intentionally NOT enabled (no rehype-raw) so user content can't
 * inject markup — links open safely in a new tab.
 */
export function Markdown({ children, className = "" }: { children: string; className?: string }) {
  return (
    <div className={`community-md text-[15px] leading-relaxed text-gray-200 ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children, ...props }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer nofollow"
              className="text-saffron underline decoration-saffron/40 underline-offset-2 hover:decoration-saffron"
              {...props}
            >
              {children}
            </a>
          ),
          p: ({ children }) => <p className="mb-3 last:mb-0 whitespace-pre-wrap">{children}</p>,
          h1: ({ children }) => <h1 className="mb-2 mt-3 font-cinzel text-xl text-gray-100">{children}</h1>,
          h2: ({ children }) => <h2 className="mb-2 mt-3 font-cinzel text-lg text-gray-100">{children}</h2>,
          h3: ({ children }) => <h3 className="mb-2 mt-3 font-cinzel text-base text-gray-100">{children}</h3>,
          ul: ({ children }) => <ul className="mb-3 list-disc space-y-1 pl-5 marker:text-saffron/70">{children}</ul>,
          ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1 pl-5 marker:text-saffron/70">{children}</ol>,
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="my-3 border-l-2 border-saffron/50 bg-saffron/5 py-1 pl-3 italic text-gray-300">
              {children}
            </blockquote>
          ),
          code: ({ children }) => (
            <code className="rounded bg-black/40 px-1.5 py-0.5 font-mono text-[13px] text-[#f0cd80]">
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="my-3 overflow-x-auto rounded-lg border border-white/10 bg-black/40 p-3 text-[13px]">
              {children}
            </pre>
          ),
          strong: ({ children }) => <strong className="font-semibold text-gray-100">{children}</strong>,
          hr: () => <hr className="my-4 border-white/10" />,
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto">
              <table className="w-full border-collapse text-sm">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-white/10 bg-white/5 px-2 py-1 text-left">{children}</th>
          ),
          td: ({ children }) => <td className="border border-white/10 px-2 py-1">{children}</td>,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
