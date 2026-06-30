"use client";

import { useEffect, useState, Suspense, useRef, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useConversations } from "@/context/ConversationContext";
import { ChatInterface } from "@/components/chat/ChatInterface";
import { SourcesPanel } from "@/components/chat/SourcesPanel";
import { SacredGeometryLoader } from "@/components/chat/SacredGeometryLoader";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation } from "@/lib/i18n";
import type { SourceRef, QueryMode } from "@/lib/api";

const MODE_MAP: Record<string, QueryMode> = {
  guide: "guide",
  research: "research",
};

function ChatContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { language } = useLanguage();
  const sessionId = searchParams.get("session");
  const rawMode = searchParams.get("mode") ?? "guide";
  const modeParam: QueryMode = MODE_MAP[rawMode] ?? "guide";
  const { ensureConversation, hydrated, newConversation } = useConversations();
  const [conversation, setConversation] = useState<any>(null);
  const [currentMode, setCurrentMode] = useState<QueryMode>(modeParam);
  const [activeSources, setActiveSources] = useState<SourceRef[]>([]);
  const [activeMessageId, setActiveMessageId] = useState<string | null>(null);
  const [activeSourceIndex, setActiveSourceIndex] = useState<number | null>(null);
  const redirectedRef = useRef(false);
  const [showUpgradeBanner, setShowUpgradeBanner] = useState(false);

  useEffect(() => {
    // Handle Research Mode Sources
    if (currentMode === "research") {
      if (conversation?.messages?.length > 0) {
        if (activeMessageId) {
          const msg = conversation.messages.find((m: any) => m.id === activeMessageId);
          if (msg && msg.sources && msg.sources.length > 0) {
            setActiveSources(msg.sources);
          } else {
            setActiveSources([]);
          }
        } else {
          const lastAsstMsg = [...conversation.messages]
            .reverse()
            .find((m: any) => m.role === 'assistant' && m.sources && m.sources.length > 0);
          if (lastAsstMsg && lastAsstMsg.sources) {
            setActiveSources(lastAsstMsg.sources);
          } else {
            setActiveSources([]);
          }
        }
      } else {
        setActiveSources([]);
      }
    } else {
      setActiveSources([]);
      setActiveSourceIndex(null);
    }
  }, [conversation?.messages, activeMessageId, currentMode]);

  useEffect(() => {
    setCurrentMode(modeParam);
  }, [modeParam]);

  useEffect(() => {
    if (searchParams.get("upgraded") === "1") {
      setShowUpgradeBanner(true);
      // Strip the param from the URL without triggering a re-render loop
      const url = new URL(window.location.href);
      url.searchParams.delete("upgraded");
      window.history.replaceState(null, "", url.toString());
      const t = setTimeout(() => setShowUpgradeBanner(false), 6000);
      return () => clearTimeout(t);
    }
  }, [searchParams]);

  useEffect(() => {
    if (!hydrated) return;

    if (!sessionId) {
      if (redirectedRef.current) return;
      redirectedRef.current = true;
      const conv = newConversation();
      router.replace(`/chat?session=${conv.sessionId}`);
      return;
    }

    const conv = ensureConversation(sessionId);
    setConversation(conv);
  }, [hydrated, sessionId, ensureConversation, newConversation, router]);

  if (!hydrated || !conversation) {
    return (
      <div className="flex h-full w-full items-center justify-center" style={{ background: '#000000' }}>
        <SacredGeometryLoader />
      </div>
    );
  }

  const showSources = currentMode === "research" && activeSources.length > 0;

  return (
    <div className="flex h-full relative">
      {/* Upgrade success banner */}
      {showUpgradeBanner && (
        <div
          className="fixed top-16 left-1/2 z-50 -translate-x-1/2 px-6 py-3 rounded-xl text-sm font-semibold text-white shadow-2xl flex items-center gap-3 animate-in fade-in slide-in-from-top-2 duration-500"
          style={{ background: 'linear-gradient(135deg, #e8b63f 0%, #b8893b 100%)', boxShadow: '0 0 32px rgba(232,182,63,0.5)', fontFamily: 'var(--font-ui)' }}
        >
          {getTranslation(language, "chat.pro_banner")}
          <button onClick={() => setShowUpgradeBanner(false)} className="ml-2 opacity-70 hover:opacity-100 text-base leading-none" aria-label="Dismiss">×</button>
        </div>
      )}

      {/* Mobile backdrop for sources panel */}
      {showSources && (
        <div
          className="fixed inset-0 z-10 bg-black/50 lg:hidden"
          onClick={() => { setActiveSources([]); }}
        />
      )}

      {/* Center: Chat */}
      <main
        className={`relative h-full flex-1 overflow-hidden transition-all duration-300 ${showSources ? "lg:mr-80" : ""}`}
      >
        <ChatInterface
          conversationId={conversation.id}
          defaultMode={modeParam}
          onSourcesChange={(sources, messageId) => {
            if (sources.length === 0) {
              setActiveSources([]);
              setActiveSourceIndex(null);
              return;
            }
            setActiveSources(sources);
            if (messageId) setActiveMessageId(messageId);
          }}
          onModeChange={setCurrentMode}
          onSourceClick={(messageId, index) => {
            setActiveMessageId(messageId);
            if (index !== undefined) setActiveSourceIndex(index);
          }}
        />
      </main>

      {/* Right: Sources panel — slides in from right, full width on mobile with close btn */}
      <aside
        className={`fixed bottom-0 right-0 top-14 z-20 h-[calc(100vh-3.5rem)] overflow-hidden border-l border-white/10 transition-all duration-300 sm:w-80 w-full max-w-[calc(100vw-48px)]`}
        style={{
          background: '#000000',
          transform: showSources ? 'translateX(0)' : 'translateX(110%)',
        }}
      >
        {/* Mobile close button */}
        {showSources && (
          <button
            onClick={() => setActiveSources([])}
            className="absolute top-3 right-3 z-30 sm:hidden w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-[#a38d7c] hover:text-white"
            aria-label="Close panel"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        )}
        <SourcesPanel sources={activeSources} activeIndex={activeSourceIndex} />
      </aside>
    </div>
  );
}

export default function ChatPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-full w-full items-center justify-center" style={{ background: '#000000' }}>
          <SacredGeometryLoader />
        </div>
      }
    >
      <ChatContent />
    </Suspense>
  );
}
