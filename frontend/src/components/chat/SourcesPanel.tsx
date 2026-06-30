'use client';

import { SourceRef, formatSourceRef } from '@/lib/api';
import Link from 'next/link';
import { useState, useEffect, useRef } from 'react';
import { useLanguage } from '@/context/LanguageContext';
import { getTranslation } from '@/lib/i18n';

interface Props {
  sources: SourceRef[];
  activeIndex?: number | null;
}

export function SourcesPanel({ sources, activeIndex }: Props) {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<(HTMLAnchorElement | null)[]>([]);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const { language } = useLanguage();
  const [visibleCount, setVisibleCount] = useState(3);

  useEffect(() => {
    setVisibleCount(3);
  }, [sources]);

  useEffect(() => {
    if (!loadMoreRef.current || visibleCount >= sources.length) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) {
        setVisibleCount(prev => Math.min(prev + 3, sources.length));
      }
    }, { root: scrollContainerRef.current, rootMargin: '100px' });
    
    observer.observe(loadMoreRef.current);
    return () => observer.disconnect();
  }, [sources.length, visibleCount]);

  useEffect(() => {
    if (activeIndex !== undefined && activeIndex !== null && itemRefs.current[activeIndex]) {
      // Ensure the active index is visible if it's beyond the current visibleCount
      if (activeIndex >= visibleCount) {
        setVisibleCount(activeIndex + 3);
      }
      setTimeout(() => {
        itemRefs.current[activeIndex]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }, 50);
    }
  }, [activeIndex, visibleCount]);

  return (
    <div className="h-full flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-white/10 flex-shrink-0 flex items-center justify-between">
        <p
          className="text-[10px] uppercase tracking-widest text-[#94a3b8]"
          style={{ fontFamily: 'var(--font-ui)', fontVariant: 'small-caps' }}
        >
          {getTranslation(language, 'ui.sources')}
        </p>
        {sources.length > 0 && (
          <span
            className="flex h-5 min-w-[1.25rem] items-center justify-center rounded-full px-1.5 text-[10px] font-bold"
            style={{ background: 'rgba(232,182,63,0.12)', border: '1px solid rgba(232,182,63,0.3)', color: '#a78bfa', fontFamily: 'var(--font-ui)' }}
          >
            {sources.length}
          </span>
        )}
      </div>

      {sources.length === 0 ? (
        /* Empty state */
        <div className="flex-1 flex flex-col items-center justify-center gap-3 p-6 text-center">
          <div
            className="text-[5rem] leading-none select-none"
            style={{ opacity: 0.07, color: '#e5e2e1' }}
          >
            ॐ
          </div>
          <p
            className="text-sm text-[#554336]"
            style={{ fontFamily: 'var(--font-ui)' }}
          >
            {getTranslation(language, 'ui.no_sources')}
          </p>
        </div>
      ) : (
        /* Source cards */
        <div
          ref={scrollContainerRef}
          className="flex-1 overflow-y-auto p-4 space-y-3"
          style={{ scrollbarWidth: 'thin', scrollbarColor: '#2a2a2a transparent' }}
        >
          {sources.slice(0, visibleCount).map((source, i) => {
            const isActive = activeIndex === i;
            return (
              <Link
                ref={(el) => { itemRefs.current[i] = el; }}
                href={
                  source.chunk_id
                    ? `/library/explore?verse=${encodeURIComponent(source.chunk_id)}`
                    : `/library/text?id=${source.text_id}&ref=${encodeURIComponent(source.reference)}`
                }
                key={i}
                className={`group block rounded-2xl p-4 cursor-pointer transition-all duration-300 ${isActive ? 'bg-gradient-to-br from-[#a78bfa]/[0.12] to-transparent ring-1 ring-inset ring-[#a78bfa]/45 shadow-[0_10px_34px_rgba(232,182,63,0.14)] -translate-y-px' : 'border border-white/[0.06] bg-[#161513] hover:-translate-y-0.5 hover:border-[#a78bfa]/30 hover:bg-white/[0.03]'}`}
              >
              {/* Top row: number badge + name + reference */}
              <div className="flex items-start justify-between gap-2 mb-1.5">
                <span className="flex min-w-0 items-center gap-2">
                  <span
                    className="flex h-[1.15rem] min-w-[1.15rem] flex-shrink-0 items-center justify-center rounded-full px-1 text-[10px] font-bold"
                    style={{
                      background: isActive ? '#a78bfa' : 'rgba(232,182,63,0.16)',
                      color: isActive ? '#0e0c09' : '#a78bfa',
                      border: '1px solid rgba(232,182,63,0.35)',
                      fontFamily: 'var(--font-ui)',
                    }}
                  >
                    {i + 1}
                  </span>
                  <span
                    className="truncate text-[11px] uppercase tracking-wider text-[#a78bfa]"
                    style={{ fontFamily: 'var(--font-ui)' }}
                  >
                    {source.text_name || source.purana}
                  </span>
                </span>
                <span
                  className="text-[11px] text-[#94a3b8] flex-shrink-0"
                  style={{ fontFamily: 'var(--font-ui)' }}
                >
                  {formatSourceRef(source)}
                </span>
              </div>

              {/* Title / purana name */}
              <p
                className="text-[15px] text-[#e5e2e1] group-hover:text-[#f0cd80] transition-colors leading-snug mb-2"
                style={{ fontFamily: 'var(--font-display)' }}
              >
                {source.purana}
              </p>

              {/* Excerpt */}
              <p
                className="text-[13px] text-[#dbc2b0] leading-relaxed line-clamp-3"
                style={{ fontFamily: 'var(--font-body)' }}
              >
                {source.text}
              </p>

              {/* View text — shown on hover */}
              <p
                className="text-[11px] text-[#a78bfa] mt-2 opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ fontFamily: 'var(--font-ui)' }}
              >
                View Text →
              </p>
              </Link>
            );
          })}
          {visibleCount < sources.length && (
            <div ref={loadMoreRef} className="h-10 w-full" />
          )}
        </div>
      )}
    </div>
  );
}
