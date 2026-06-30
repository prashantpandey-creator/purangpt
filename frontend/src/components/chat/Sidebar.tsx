"use client";

import { Trash2, Settings, Pencil, Check, ChevronsLeft, ChevronsRight, Volume2, VolumeX, LogOut, User, Info } from "lucide-react";
import { FlameIcon, YantraEyeIcon, SanghaIcon, PothiIcon, ScrollIcon, LotusIcon, NadaIcon } from "@/components/icons/SacredIcons";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { ConcentricBindu } from "@/components/ui/ConcentricBindu";
import { useConversations, type Conversation } from "@/context/ConversationContext";
import { useUI } from "@/context/UIPreferencesContext";
import { useAuth } from "@/context/AuthContext";
import { useToast } from "@/context/ToastContext";
import { useEffect, useMemo, useRef, useState } from "react";
import { LanguageSelector } from "@/components/ui/LanguageSelector";
import { Wordmark } from "@/components/ui/Logo";
import { useLanguage } from "@/context/LanguageContext";
import { getTranslation } from "@/lib/i18n";
import { useSound } from "@/hooks/useSound";
import { getHumEnabled, toggleHum, subscribeHum, requestHumBoot } from "@/lib/humControl";
import { SignInModal } from "@/components/auth/SignInModal";

/** Bucket conversations into human date groups, most-recent first. */
function groupConversations(convos: Conversation[]) {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startOfYesterday = startOfToday - 86_400_000;
  const start7Days = startOfToday - 6 * 86_400_000;

  const groups: { key: string; items: Conversation[] }[] = [
    { key: "sidebar.today", items: [] },
    { key: "sidebar.yesterday", items: [] },
    { key: "sidebar.prev_7_days", items: [] },
    { key: "sidebar.older", items: [] },
  ];

  for (const c of [...convos].sort((a, b) => b.updatedAt - a.updatedAt)) {
    const t = c.updatedAt;
    if (t >= startOfToday) groups[0].items.push(c);
    else if (t >= startOfYesterday) groups[1].items.push(c);
    else if (t >= start7Days) groups[2].items.push(c);
    else groups[3].items.push(c);
  }
  return groups.filter((g) => g.items.length > 0);
}

export function Sidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const { setSidebarOpen, sidebarCollapsed, toggleSidebarCollapsed, setSidebarCollapsed } = useUI();
  const { user, profile, signOut, initialized } = useAuth();
  const { toast } = useToast();
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const accountRef = useRef<HTMLDivElement | null>(null);
  const { language } = useLanguage();
  const { playClick } = useSound();
  const {
    conversations,
    activeId,
    hydrated,
    newConversation,
    deleteConversation,
    renameConversation,
  } = useConversations();

  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const renameInputRef = useRef<HTMLInputElement>(null);
  const activeItemRef = useRef<HTMLDivElement | null>(null);

  const isPro = ["pro", "scholar", "admin"].includes(profile?.plan || "free");
  const collapsed = sidebarCollapsed;
  // Per-element collapse helpers: hide labels, center icon rows on desktop.
  const lbl = collapsed ? "lg:hidden" : "";
  const rowJustify = collapsed ? "lg:justify-center lg:px-0" : "";

  const groups = useMemo(() => groupConversations(conversations), [conversations]);

  // Close the account popover on outside click.
  useEffect(() => {
    if (!accountMenuOpen) return;
    const handler = (e: MouseEvent) => {
      if (accountRef.current && !accountRef.current.contains(e.target as Node)) setAccountMenuOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [accountMenuOpen]);

  // Keep the active conversation visible when history loads or selection changes.
  useEffect(() => {
    if (hydrated && activeId) {
      activeItemRef.current?.scrollIntoView({ block: "nearest" });
    }
  }, [hydrated, activeId, groups.length]);

  const startRename = (conv: Conversation) => {
    setEditingId(conv.id);
    setDraftTitle(conv.title);
    requestAnimationFrame(() => renameInputRef.current?.select());
  };

  const commitRename = () => {
    if (editingId) renameConversation(editingId, draftTitle);
    setEditingId(null);
  };

  const handleNewChat = () => {
    playClick();
    const conv = newConversation();
    router.push(`/chat?session=${conv.sessionId}`);
    setSidebarOpen(false);
  };

  const handleDeleteConversation = (
    e: React.MouseEvent,
    id: string,
    activeConvId: string | null
  ) => {
    e.stopPropagation();
    playClick();
    deleteConversation(id);
    if (id === activeConvId) {
      router.push("/chat");
    }
  };

  const userInitials = user?.email
    ? user.email.slice(0, 2).toUpperCase()
    : "ॐ";

  const handleSignOut = async () => {
    setAccountMenuOpen(false);
    try {
      await signOut();
      toast("Signed out", "success");
      router.push("/");
    } catch {
      toast("Failed to sign out", "error");
    }
  };

  return (
    <>
    <aside
      className={`flex flex-col overflow-hidden safe-pt safe-pb transition-[width] duration-300 ease-in-out w-64 ${collapsed ? "sidebar-collapsed" : ""}`}
      style={{
        background: 'rgba(10,8,16,0.55)',
        backdropFilter: 'blur(18px)',
        WebkitBackdropFilter: 'blur(18px)',
        borderRight: '1px solid rgba(139,92,246,0.12)',
        height: '100dvh',
      }}
    >
      {/* Logo row + desktop collapse chevron */}
      <div
        className={`flex items-center gap-2 px-3 py-3.5 flex-shrink-0 ${collapsed ? "lg:flex-col lg:gap-2 lg:px-0" : ""}`}
        style={{ borderBottom: '1px solid rgba(139,92,246,0.12)' }}
      >
        <Link
          href="/"
          className="flex items-center gap-3 group min-w-0"
          onClick={() => {
            playClick();
            setSidebarOpen(false);
          }}
          aria-label="PuranGPT home"
        >
          <span className="flex-shrink-0 transition-all group-hover:scale-110 drop-shadow-[0_0_8px_rgba(139,92,246,0.4)]">
            <ConcentricBindu size={collapsed ? 36 : 40} />
          </span>
          <span className={lbl}><Wordmark tagline={null} /></span>
        </Link>
        <button
          onClick={() => { playClick(); toggleSidebarCollapsed(); }}
          className={`hidden lg:flex items-center justify-center w-8 h-8 rounded-lg flex-shrink-0 transition-all hover:bg-[#7c3aed]/10 ${collapsed ? "" : "ml-auto"}`}
          style={{ color: '#7c3aed', opacity: 0.5, border: '1px solid rgba(124,58,237,0.20)' }}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          title={collapsed ? "Expand" : "Collapse"}
        >
          {collapsed ? <ChevronsRight className="w-4 h-4" /> : <ChevronsLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* ── Features zone — surfaces all the site's capabilities ─────────── */}
      <div className="px-3 pt-3 flex-shrink-0">
        <p
          className={`px-2 mb-1.5 text-[10px] uppercase tracking-[0.14em] ${lbl}`}
          style={{ fontFamily: 'var(--font-sidebar)', color: '#6b5a3a' }}
        >
          Explore
        </p>

        <div className="space-y-1">
          {/* New Chat — primary action, saffron accent */}
          <button
            onClick={handleNewChat}
            className={`group/feat w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-semibold transition-all hover:bg-[#7c3aed]/10 ${rowJustify}`}
            style={{
              border: '1px solid rgba(139,92,246,0.4)',
              background: 'rgba(139,92,246,0.06)',
              color: '#a78bfa',
              fontFamily: 'var(--font-sidebar)',
            }}
            aria-label="Start new chat"
            title={getTranslation(language, "nav.new_inquiry")}
          >
            <span
              className="flex items-center justify-center w-7 h-7 rounded-lg flex-shrink-0 transition-all group-hover/feat:scale-105"
              style={{ background: 'rgba(139,92,246,0.16)', boxShadow: 'var(--glow-gold-sm)' }}
            >
              <FlameIcon className="w-4 h-4" />
            </span>
            <span className={lbl}>{getTranslation(language, "nav.new_inquiry")}</span>
          </button>

          {/* Voice Darshan — speak, the Guru answers aloud */}
          <FeatureRow
            href="/darshan"
            label="Voice Darshan"
            icon={<NadaIcon className="w-[18px] h-[18px]" />}
            active={pathname?.startsWith("/darshan") ?? false}
            onClick={playClick}
            collapsed={collapsed}
          />

          {/* Deep Research — Pro, web-grounded research mode */}
          <FeatureRow
            href="/dashboard/deep-research"
            label={getTranslation(language, "nav.research")}
            icon={<YantraEyeIcon className="w-[18px] h-[18px]" />}
            active={pathname?.startsWith("/dashboard/deep-research") ?? false}
            onClick={playClick}
            badge={!isPro ? "PRO" : undefined}
            collapsed={collapsed}
          />

          {/* Community */}
          <FeatureRow
            href="/community"
            label="Community"
            icon={<SanghaIcon className="w-[18px] h-[18px]" />}
            active={pathname?.startsWith("/community") ?? false}
            onClick={playClick}
            collapsed={collapsed}
          />

          {/* Text Library */}
          <FeatureRow
            href="/library"
            label={getTranslation(language, "nav.text_library")}
            icon={<PothiIcon className="w-[18px] h-[18px]" />}
            active={pathname?.startsWith("/library") ?? false}
            onClick={playClick}
            collapsed={collapsed}
          />

          {/* Workspace */}
          <FeatureRow
            href="/workspace"
            label="Workspace"
            icon={<ScrollIcon className="w-[18px] h-[18px]" />}
            active={pathname?.startsWith("/workspace") ?? false}
            onClick={playClick}
            collapsed={collapsed}
          />

          {/* About PuranGPT */}
          <FeatureRow
            href="/about"
            label="About PuranGPT"
            icon={<LotusIcon className="w-[18px] h-[18px]" />}
            active={pathname?.startsWith("/about") ?? false}
            onClick={playClick}
            collapsed={collapsed}
          />
        </div>
      </div>

      {/* ── Conversations zone (hidden in the collapsed rail) ──────────────── */}
      <div className={`mt-3 flex-1 overflow-hidden flex flex-col min-h-0 ${collapsed ? "lg:hidden" : ""}`}>
        <p
          className="px-5 mb-1.5 text-[10px] uppercase tracking-[0.14em] flex-shrink-0"
          style={{ fontFamily: 'var(--font-sidebar)', color: '#6b5a3a' }}
        >
          History
        </p>

        {!hydrated ? (
          /* Skeleton while history hydrates from storage */
          <div className="flex-1 pt-1">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="convo-skeleton" style={{ opacity: 1 - i * 0.16 }} />
            ))}
          </div>
        ) : conversations.length === 0 ? (
          <div className="px-5 pt-1 pb-4">
            <p
              className="text-xs leading-relaxed"
              style={{ fontFamily: 'var(--font-sidebar)', color: '#7c3aed', opacity: 0.5 }}
            >
              Your conversations will appear here.
            </p>
          </div>
        ) : (
          <div
            className="flex-1 overflow-y-auto pr-1"
            style={{ scrollbarWidth: 'thin', scrollbarColor: '#1a1a1a transparent', WebkitOverflowScrolling: 'touch' }}
          >
            {groups.map((group) => (
              <div key={group.key} className="mb-2">
                <p
                  className="px-5 mb-1 text-[10px] uppercase tracking-[0.12em]"
                  style={{ fontFamily: 'var(--font-sidebar)', color: '#7c3aed', opacity: 0.5 }}
                >
                  {getTranslation(language, group.key as Parameters<typeof getTranslation>[1])}
                </p>
                <div className="space-y-0.5">
                  {group.items.map((conv) => {
                    const active = conv.id === activeId;
                    const editing = editingId === conv.id;
                    return (
                      <div
                        key={conv.id}
                        ref={active ? activeItemRef : undefined}
                        className={`group relative flex items-center gap-1.5 border-l-2 pl-5 pr-2 text-[15px] transition-colors ${
                          active
                            ? 'border-[#7c3aed] bg-[#7c3aed]/8'
                            : 'border-transparent hover:bg-white/[0.03]'
                        }`}
                        style={{ borderColor: active ? '#7c3aed' : 'transparent' }}
                      >
                        <svg viewBox="0 0 24 24" fill="none" className="w-4 h-4 flex-shrink-0 opacity-50" style={{ color: active ? '#a78bfa' : '#94a3b8' }}>
                          <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="1.5" />
                          <path d="M12 7v5l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>

                        {editing ? (
                          <input
                            ref={renameInputRef}
                            value={draftTitle}
                            onChange={(e) => setDraftTitle(e.target.value)}
                            onBlur={commitRename}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') { e.preventDefault(); commitRename(); }
                              if (e.key === 'Escape') { e.preventDefault(); setEditingId(null); }
                            }}
                            className="flex-1 min-w-0 bg-transparent py-2 text-sm focus:outline-none"
                            style={{ fontFamily: 'var(--font-sidebar)', color: '#a78bfa' }}
                            aria-label="Rename conversation"
                          />
                        ) : (
                          <button
                            className="flex-1 min-w-0 text-left truncate py-2 transition-colors"
                            style={{ fontFamily: 'var(--font-sidebar)', color: active ? '#a78bfa' : '#94a3b8' }}
                            onClick={() => {
                              playClick();
                              router.push(`/chat?session=${conv.sessionId}`);
                              setSidebarOpen(false);
                            }}
                            onDoubleClick={() => startRename(conv)}
                          >
                            {conv.title}
                          </button>
                        )}

                        {editing ? (
                          <button
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={commitRename}
                            className="flex-shrink-0 p-0.5 transition-colors hover:text-[#7c3aed]"
                            style={{ color: '#94a3b8' }}
                            aria-label="Save title"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                        ) : (
                          <div className="hover-reveal flex flex-shrink-0 items-center">
                            <button
                              onClick={() => { playClick(); startRename(conv); }}
                              className="p-1.5 transition-colors hover:text-[#7c3aed]"
                              style={{ color: '#94a3b8' }}
                              aria-label="Rename conversation"
                            >
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={(e) => {
                                playClick();
                                handleDeleteConversation(e, conv.id, activeId);
                              }}
                              className="p-1.5 transition-colors hover:text-red-500"
                              style={{ color: '#94a3b8' }}
                              aria-label="Delete conversation"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* In the collapsed rail the history zone is hidden, so a spacer pushes
          the footer to the bottom. */}
      {collapsed && <div className="hidden lg:block flex-1" />}

      {/* ── Footer: Nāda · language · account (all former topbar controls) ── */}
      <div
        className={`flex-shrink-0 p-3 space-y-2 ${collapsed ? "lg:px-2" : ""}`}
        style={{ borderTop: '1px solid rgba(139,92,246,0.12)' }}
      >
        {/* Nāda (cosmic hum) toggle — moved out of the old topbar */}
        <HumToggle collapsed={collapsed} />

        <div className={`flex items-center ${collapsed ? "lg:justify-center" : "justify-center"}`}>
          {/* Full selector when expanded; compact globe icon in the collapsed rail */}
          <div className={collapsed ? "hidden lg:block" : ""}>
            <LanguageSelector openDirection="up" compact={collapsed} />
          </div>
          <div className={collapsed ? "lg:hidden" : "hidden"}>
            <LanguageSelector openDirection="up" />
          </div>
        </div>

        {/* Account */}
        {initialized && user ? (
          <div className="relative" ref={accountRef}>
            <button
              onClick={() => {
                playClick();
                // In the collapsed rail there's no room for the popover — expand first.
                if (collapsed && window.innerWidth >= 1024) { setSidebarCollapsed(false); return; }
                setAccountMenuOpen((v) => !v);
              }}
              className={`w-full flex items-center gap-3 p-2 rounded-2xl transition-colors hover:bg-white/[0.04] ${rowJustify}`}
              aria-label="Account menu"
              aria-expanded={accountMenuOpen}
            >
              <span
                className="w-8 h-8 rounded-full flex items-center justify-center text-xs flex-shrink-0"
                style={{
                  background: 'rgba(139,92,246,0.15)',
                  border: '1px solid rgba(139,92,246,0.3)',
                  color: '#7c3aed',
                  fontFamily: 'var(--font-sidebar)',
                }}
              >
                {userInitials}
              </span>
              <span className={`flex-1 min-w-0 text-left ${lbl}`}>
                <span className="block truncate" style={{ fontSize: 15, color: '#a78bfa', fontWeight: 600 }}>
                  {user.email?.split('@')[0]}
                </span>
                <span className="block truncate" style={{ fontSize: 12, color: '#7c3aed', opacity: 0.55, fontFamily: 'var(--font-sidebar)' }}>
                  {user.email}
                </span>
              </span>
              <span
                className={`flex-shrink-0 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-md font-semibold ${lbl} ${isPro ? 'bg-[#7c3aed]/10 border border-[#7c3aed]/30 text-[#7c3aed]' : 'bg-white/5 border border-white/10 text-[#94a3b8]'}`}
              >
                {isPro ? "Pro" : "Free"}
              </span>
            </button>

            {accountMenuOpen && (
              <div
                className="absolute bottom-full left-0 right-0 mb-2 rounded-2xl overflow-hidden z-50 animate-fade-in"
                style={{ background: 'rgba(10,9,8,0.98)', border: '1px solid rgba(139,92,246,0.2)', backdropFilter: 'blur(16px)' }}
              >
                <AccountLink href="/profile" icon={<User className="w-4 h-4" />} label="Profile" onClick={() => { playClick(); setAccountMenuOpen(false); }} />
                {user.sub && (
                  <AccountLink href={`/community/u/${encodeURIComponent(user.sub)}`} icon={<SanghaIcon className="w-4 h-4" />} label="Community Profile" onClick={() => { playClick(); setAccountMenuOpen(false); }} />
                )}
                <AccountLink href="/settings" icon={<Settings className="w-4 h-4" />} label="Settings" onClick={() => { playClick(); setAccountMenuOpen(false); }} />
                <AccountLink href="/about" icon={<Info className="w-4 h-4" />} label="Introduction" onClick={() => { playClick(); setAccountMenuOpen(false); }} />
                <div style={{ borderTop: '1px solid rgba(139,92,246,0.1)' }} />
                <button
                  onClick={handleSignOut}
                  className="w-full text-left px-4 py-2.5 text-sm transition-colors hover:bg-red-900/20 flex items-center gap-2.5"
                  style={{ color: '#94a3b8', fontFamily: 'var(--font-sidebar)' }}
                >
                  <LogOut className="w-4 h-4" />
                  Logout
                </button>
              </div>
            )}
          </div>
        ) : (
          <button
            onClick={() => { playClick(); setAuthModalOpen(true); }}
            className={`w-full flex items-center justify-center gap-2 py-2.5 rounded-2xl transition-all border border-[#7c3aed]/35 text-[#a78bfa] bg-[#7c3aed]/8 hover:bg-[#7c3aed]/18 text-sm font-semibold ${rowJustify}`}
            style={{ fontFamily: 'var(--font-sidebar)' }}
            aria-label={getTranslation(language, "nav.sign_in")}
            title={getTranslation(language, "nav.sign_in")}
          >
            <User className="w-4 h-4 flex-shrink-0" />
            <span className={lbl}>{getTranslation(language, "nav.sign_in")}</span>
          </button>
        )}
      </div>
    </aside>
    <SignInModal isOpen={authModalOpen} onClose={() => setAuthModalOpen(false)} />
    </>
  );
}

/** A single feature row in the "Explore" zone: icon + label, rounded-xl hover,
 *  with an active-route highlight and an optional subtle PRO badge. */
function FeatureRow({
  href,
  label,
  icon,
  active,
  onClick,
  badge,
  collapsed,
}: {
  href: string;
  label: string;
  icon: React.ReactNode;
  active: boolean;
  onClick: () => void;
  badge?: string;
  collapsed?: boolean;
}) {
  const lbl = collapsed ? "lg:hidden" : "";
  return (
    <Link
      href={href}
      onClick={onClick}
      aria-label={label}
      title={label}
      aria-current={active ? "page" : undefined}
      className={`group/feat w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm transition-all ${
        active ? '' : 'hover:bg-white/[0.04]'
      } ${collapsed ? "lg:justify-center lg:px-0" : ""}`}
      style={{
        fontFamily: 'var(--font-sidebar)',
        color: active ? '#a78bfa' : '#94a3b8',
        background: active ? 'rgba(139,92,246,0.08)' : 'transparent',
        border: active ? '1px solid rgba(139,92,246,0.22)' : '1px solid transparent',
      }}
    >
      <span
        className="flex items-center justify-center w-7 h-7 rounded-lg flex-shrink-0 transition-all group-hover/feat:scale-105"
        style={{
          background: active ? 'rgba(139,92,246,0.14)' : 'rgba(255,255,255,0.03)',
          color: active ? '#a78bfa' : '#7c3aed', opacity: 0.45,
        }}
      >
        {icon}
      </span>
      <span className={`flex-1 min-w-0 truncate text-left group-hover/feat:text-[#e2d4b2] transition-colors ${lbl}`}>
        {label}
      </span>
      {badge && (
        <span className={`flex-shrink-0 text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded-md bg-[#7c3aed]/12 border border-[#7c3aed]/30 text-[#7c3aed] font-semibold ${lbl}`}>
          {badge}
        </span>
      )}
    </Link>
  );
}

/** Nāda (cosmic hum) toggle — off by default; first click boots the audio engine. */
function HumToggle({ collapsed }: { collapsed: boolean }) {
  const [on, setOn] = useState(false);
  const { playClick } = useSound();
  useEffect(() => {
    setOn(getHumEnabled());
    const unsub = subscribeHum(setOn);
    return () => { unsub(); };
  }, []);
  return (
    <button
      onClick={() => {
        playClick();
        if (!on) {
          requestHumBoot(); // first activation — boots AudioContext inside gesture
          setOn(true);
        } else {
          setOn(toggleHum());
        }
      }}
      className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm transition-all hover:bg-white/[0.04] ${collapsed ? "lg:justify-center lg:px-0" : ""}`}
      style={{ color: on ? '#a78bfa' : '#94a3b8', fontFamily: 'var(--font-sidebar)' }}
      aria-pressed={on}
      aria-label={on ? "Silence the Nāda" : "Sound the Nāda"}
      title={on ? "Nāda — sounding" : "Nāda — silent"}
    >
      <span
        className="flex items-center justify-center w-7 h-7 rounded-lg flex-shrink-0"
        style={{
          background: on ? 'rgba(139,92,246,0.10)' : 'rgba(255,255,255,0.03)',
          border: '1px solid rgba(139,92,246,0.22)',
          boxShadow: on ? '0 0 8px rgba(139,92,246,0.12)' : 'none',
        }}
      >
        {on ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
      </span>
      <span className={`flex-1 text-left ${collapsed ? "lg:hidden" : ""}`}>
        {on ? "Nāda — sounding" : "Nāda — silent"}
      </span>
    </button>
  );
}

/** A single item in the account popover menu. */
function AccountLink({ href, icon, label, onClick }: { href: string; icon: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className="flex items-center gap-2.5 px-4 py-2.5 text-sm transition-colors hover:bg-white/5"
      style={{ color: '#94a3b8', fontFamily: 'var(--font-sidebar)' }}
    >
      {icon}
      {label}
    </Link>
  );
}
