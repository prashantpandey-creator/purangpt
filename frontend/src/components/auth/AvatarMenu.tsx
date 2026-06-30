'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Settings, LogOut, Crown, Zap, Users } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';
import { useSubscription } from '@/context/SubscriptionContext';

interface AvatarMenuProps {
  user: {
    sub?: string;
    name?: string;
    email?: string;
    picture?: string;
    display_name?: string | null;
  };
}

export function AvatarMenu({ user }: AvatarMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const { signOut } = useAuth();
  const { isPro } = useSubscription();

  const displayName = user.display_name || user.name || user.email?.split('@')[0] || '…';
  const initials = displayName.slice(0, 2).toUpperCase();

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSignOut = async () => {
    setOpen(false);
    await signOut();
    router.push('/');
  };

  return (
    <div className="relative" ref={ref}>
      {/* Avatar button */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative flex items-center gap-2.5 group"
        aria-label="Open account menu"
        aria-expanded={open}
      >
        {/* Avatar circle */}
        <div className={`relative w-8 h-8 rounded-full overflow-hidden flex-shrink-0 ${isPro ? 'ring-2 ring-[#a78bfa] ring-offset-1 ring-offset-[#000000]' : 'ring-1 ring-white/20'}`}>
          {user.picture ? (
            <img
              src={user.picture}
              alt={displayName}
              className="w-full h-full object-cover"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="w-full h-full bg-[#a78bfa]/20 flex items-center justify-center text-[#a78bfa] text-xs font-bold">
              {initials}
            </div>
          )}
          {/* Pro crown badge */}
          {isPro && (
            <div className="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 bg-[#a78bfa] rounded-full flex items-center justify-center">
              <Crown className="w-2 h-2 text-[#000000]" />
            </div>
          )}
        </div>
        {/* Name (hidden on small screens) */}
        <span
          className="hidden sm:block text-sm text-[#e5e2e1] group-hover:text-white transition-colors max-w-[120px] truncate"
          style={{ fontFamily: 'var(--font-ui)' }}
        >
          {displayName}
        </span>
      </button>

      {/* Dropdown */}
      {open && (
        <div
          className="absolute right-0 top-full mt-2 w-64 rounded-2xl border border-white/10 shadow-2xl z-[200] overflow-hidden"
          style={{ background: 'rgba(20,19,19,0.98)', backdropFilter: 'blur(20px)' }}
        >
          {/* Header */}
          <div className="px-4 py-4 border-b border-white/10">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-full overflow-hidden flex-shrink-0 ${isPro ? 'ring-2 ring-[#a78bfa]' : 'ring-1 ring-white/20'}`}>
                {user.picture ? (
                  <img src={user.picture} alt={displayName} className="w-full h-full object-cover" referrerPolicy="no-referrer" />
                ) : (
                  <div className="w-full h-full bg-[#a78bfa]/20 flex items-center justify-center text-[#a78bfa] text-sm font-bold">{initials}</div>
                )}
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium text-[#e5e2e1] truncate">{displayName}</p>
                <p className="text-xs text-[#94a3b8] truncate">{user.email}</p>
              </div>
            </div>

            {/* Plan badge */}
            <div className={`mt-3 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium ${
              isPro
                ? 'bg-[#a78bfa]/15 text-[#a78bfa] border border-[#a78bfa]/30'
                : 'bg-white/5 text-[#94a3b8] border border-white/10'
            }`}
              style={{ fontFamily: 'var(--font-ui)' }}
            >
              {isPro ? <Crown className="w-3 h-3" /> : <Zap className="w-3 h-3" />}
              {isPro ? 'Pro' : 'Free Plan'}
            </div>
          </div>

          {/* Menu items */}
          <div className="py-1.5">
            {!isPro && (
              <Link
                href="/pricing"
                onClick={() => setOpen(false)}
                className="flex items-center gap-3 px-4 py-2.5 text-sm text-[#a78bfa] hover:bg-[#a78bfa]/10 transition-colors"
                style={{ fontFamily: 'var(--font-ui)' }}
              >
                <Crown className="w-4 h-4" />
                Upgrade to Pro
              </Link>
            )}
            {user.sub && (
              <Link
                href={`/community/u/${encodeURIComponent(user.sub)}`}
                onClick={() => setOpen(false)}
                className="flex items-center gap-3 px-4 py-2.5 text-sm text-[#94a3b8] hover:bg-white/5 hover:text-[#e5e2e1] transition-colors"
                style={{ fontFamily: 'var(--font-ui)' }}
              >
                <Users className="w-4 h-4" />
                Community Profile
              </Link>
            )}
            <Link
              href="/settings"
              onClick={() => setOpen(false)}
              className="flex items-center gap-3 px-4 py-2.5 text-sm text-[#94a3b8] hover:bg-white/5 hover:text-[#e5e2e1] transition-colors"
              style={{ fontFamily: 'var(--font-ui)' }}
            >
              <Settings className="w-4 h-4" />
              Settings
            </Link>
            <div className="border-t border-white/10 mt-1 pt-1">
              <button
                onClick={handleSignOut}
                className="w-full flex items-center gap-3 px-4 py-2.5 text-sm text-[#94a3b8] hover:bg-white/5 hover:text-red-400 transition-colors"
                style={{ fontFamily: 'var(--font-ui)' }}
              >
                <LogOut className="w-4 h-4" />
                Sign out
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
