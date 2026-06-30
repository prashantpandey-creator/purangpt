"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * GrowthDashboard — the control panel for the growth_engine.
 *
 * Every call goes through /api/growth/<...>, the server-side proxy that gates on
 * the session cookie and forwards identity to the FastAPI. The browser never
 * sees the engine URL or any service key; connection secrets are POSTed once and
 * encrypted server-side (Fernet vault) — they never come back in any response.
 */

type Connection = { channel: string; mode: string; handle?: string | null };
type Campaign = {
  id: string;
  name: string;
  app_slug: string;
  status: string;
  created_at: string;
};
type QueueItem = {
  id: string;
  channel: string;
  mode: string;
  status: string;
  scheduled_for: string;
  payload?: { text?: string } | null;
};

const CHANNELS: { id: string; label: string; fields: string[] }[] = [
  {
    id: "x_twitter",
    label: "X (Twitter)",
    fields: [
      "consumer_key",
      "consumer_secret",
      "access_token",
      "access_token_secret",
    ],
  },
  { id: "telegram", label: "Telegram", fields: ["bot_token", "chat_id"] },
];

async function api(path: string, init?: RequestInit) {
  const res = await fetch(`/api/growth/${path}`, init);
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new Error(data?.error || `Request failed (${res.status})`);
  return data;
}

export function GrowthDashboard() {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [conns, camps, q] = await Promise.all([
        api("connections").catch(() => []),
        api("campaigns").catch(() => []),
        api("queue").catch(() => []),
      ]);
      setConnections(Array.isArray(conns) ? conns : []);
      setCampaigns(Array.isArray(camps) ? camps : []);
      setQueue(Array.isArray(q) ? q : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="flex flex-col gap-8">
      {error && (
        <div className="glass-panel rounded-xl px-5 py-4 border-red-500/30 text-red-300 text-sm">
          {error}
        </div>
      )}

      <ConnectionsCard
        connections={connections}
        onChange={refresh}
        loading={loading}
      />
      <CampaignsCard campaigns={campaigns} onChange={refresh} />
      <QueueCard queue={queue} onChange={refresh} />
    </div>
  );
}

/* ── Connections ──────────────────────────────────────────────────────────── */

function ConnectionsCard({
  connections,
  onChange,
  loading,
}: {
  connections: Connection[];
  onChange: () => void;
  loading: boolean;
}) {
  const [openChannel, setOpenChannel] = useState<string | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [handle, setHandle] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const connected = new Set(connections.map((c) => c.channel));

  async function save(channel: string) {
    setSaving(true);
    setSaveError(null);
    try {
      await api("connections", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ channel, keys: values, handle: handle || null }),
      });
      setOpenChannel(null);
      setValues({});
      setHandle("");
      onChange();
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Section title="Channels" subtitle="Connect an account to let the engine post.">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {CHANNELS.map((ch) => {
          const isConnected = connected.has(ch.id);
          const isOpen = openChannel === ch.id;
          return (
            <div key={ch.id} className="glass-panel rounded-2xl p-5 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span
                  className="text-lg text-[#e5e2e1]"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  {ch.label}
                </span>
                {isConnected ? (
                  <span className="text-xs text-emerald-300 uppercase tracking-wide">
                    Connected
                  </span>
                ) : (
                  <span className="text-xs text-[#a38d7c] uppercase tracking-wide">
                    Not connected
                  </span>
                )}
              </div>

              {!isOpen ? (
                <button
                  className="btn-secondary text-sm self-start"
                  onClick={() => {
                    setOpenChannel(ch.id);
                    setValues({});
                    setSaveError(null);
                  }}
                  disabled={loading}
                >
                  {isConnected ? "Update keys" : "Connect"}
                </button>
              ) : (
                <div className="flex flex-col gap-2">
                  {ch.fields.map((f) => (
                    <input
                      key={f}
                      type="password"
                      placeholder={f}
                      autoComplete="off"
                      className="w-full rounded-lg bg-black/30 border border-[#b8893b]/30 px-3 py-2 text-sm text-[#e5e2e1] placeholder:text-[#6b5d4f] focus:border-[#f0cd80]/50 outline-none"
                      value={values[f] || ""}
                      onChange={(e) =>
                        setValues((v) => ({ ...v, [f]: e.target.value }))
                      }
                    />
                  ))}
                  <input
                    type="text"
                    placeholder="handle (optional, e.g. purangpt)"
                    className="w-full rounded-lg bg-black/30 border border-[#b8893b]/30 px-3 py-2 text-sm text-[#e5e2e1] placeholder:text-[#6b5d4f] focus:border-[#f0cd80]/50 outline-none"
                    value={handle}
                    onChange={(e) => setHandle(e.target.value)}
                  />
                  {saveError && (
                    <span className="text-xs text-red-300">{saveError}</span>
                  )}
                  <div className="flex gap-2">
                    <button
                      className="btn-primary text-sm"
                      onClick={() => save(ch.id)}
                      disabled={saving || ch.fields.some((f) => !values[f])}
                    >
                      {saving ? "Saving…" : "Save securely"}
                    </button>
                    <button
                      className="btn-secondary text-sm"
                      onClick={() => setOpenChannel(null)}
                      disabled={saving}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Section>
  );
}

/* ── Campaigns ────────────────────────────────────────────────────────────── */

function CampaignsCard({
  campaigns,
  onChange,
}: {
  campaigns: Campaign[];
  onChange: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [audience, setAudience] = useState("");
  const [creating, setCreating] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function create() {
    setCreating(true);
    setErr(null);
    try {
      await api("campaigns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          audience,
          channels: ["x_twitter", "telegram"],
          cadence: "daily",
          goal: "awareness",
        }),
      });
      setOpen(false);
      setName("");
      setAudience("");
      onChange();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to create");
    } finally {
      setCreating(false);
    }
  }

  return (
    <Section
      title="Campaigns"
      subtitle="A campaign decides what to post, where, and how often."
      action={
        <button className="btn-secondary text-sm" onClick={() => setOpen((o) => !o)}>
          {open ? "Close" : "New campaign"}
        </button>
      }
    >
      {open && (
        <div className="glass-panel rounded-2xl p-5 mb-4 flex flex-col gap-2">
          <input
            type="text"
            placeholder="Campaign name (e.g. Daily Gita Verse)"
            className="w-full rounded-lg bg-black/30 border border-[#b8893b]/30 px-3 py-2 text-sm text-[#e5e2e1] placeholder:text-[#6b5d4f] focus:border-[#f0cd80]/50 outline-none"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <input
            type="text"
            placeholder="Audience (e.g. seekers of Hindu philosophy)"
            className="w-full rounded-lg bg-black/30 border border-[#b8893b]/30 px-3 py-2 text-sm text-[#e5e2e1] placeholder:text-[#6b5d4f] focus:border-[#f0cd80]/50 outline-none"
            value={audience}
            onChange={(e) => setAudience(e.target.value)}
          />
          {err && <span className="text-xs text-red-300">{err}</span>}
          <button
            className="btn-primary text-sm self-start"
            onClick={create}
            disabled={creating || !name || !audience}
          >
            {creating ? "Creating…" : "Launch daily campaign"}
          </button>
        </div>
      )}

      {campaigns.length === 0 ? (
        <Empty>No campaigns yet. Create one to start the autopilot.</Empty>
      ) : (
        <ul className="flex flex-col gap-2">
          {campaigns.map((c) => (
            <li
              key={c.id}
              className="glass-panel rounded-xl px-5 py-4 flex items-center justify-between"
            >
              <span
                className="text-[#e5e2e1]"
                style={{ fontFamily: "var(--font-display)" }}
              >
                {c.name}
              </span>
              <span className="text-xs text-[#a38d7c] uppercase tracking-wide">
                {c.status}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

/* ── Approval queue ───────────────────────────────────────────────────────── */

function QueueCard({
  queue,
  onChange,
}: {
  queue: QueueItem[];
  onChange: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);

  async function act(id: string, decision: "approve" | "reject") {
    setBusy(id);
    try {
      await api(`queue/${id}/${decision}`, { method: "POST" });
      onChange();
    } finally {
      setBusy(null);
    }
  }

  return (
    <Section
      title="Approval queue"
      subtitle="Posts for channels that ban automation wait here for your one-tap yes."
    >
      {queue.length === 0 ? (
        <Empty>Nothing waiting. Auto channels post on their own.</Empty>
      ) : (
        <ul className="flex flex-col gap-3">
          {queue.map((q) => (
            <li key={q.id} className="glass-panel rounded-xl px-5 py-4 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase tracking-widest text-[#f0cd80]">
                  {q.channel}
                </span>
                <span className="text-xs text-[#a38d7c]">{q.status}</span>
              </div>
              <p
                className="text-sm text-[#e5e2e1] leading-relaxed"
                style={{ fontFamily: "var(--font-body)" }}
              >
                {q.payload?.text || "(content generated at publish time)"}
              </p>
              <div className="flex gap-2">
                <button
                  className="btn-primary text-sm"
                  onClick={() => act(q.id, "approve")}
                  disabled={busy === q.id}
                >
                  {busy === q.id ? "…" : "Approve"}
                </button>
                <button
                  className="btn-secondary text-sm"
                  onClick={() => act(q.id, "reject")}
                  disabled={busy === q.id}
                >
                  Reject
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

/* ── Shared UI ────────────────────────────────────────────────────────────── */

function Section({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section>
      <div className="flex items-start justify-between mb-4">
        <div>
          <h2
            className="text-2xl text-[#f0cd80]"
            style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}
          >
            {title}
          </h2>
          {subtitle && (
            <p
              className="text-sm text-[#a38d7c] mt-1"
              style={{ fontFamily: "var(--font-body)" }}
            >
              {subtitle}
            </p>
          )}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="glass-panel rounded-xl px-5 py-8 text-center text-sm text-[#a38d7c]"
      style={{ fontFamily: "var(--font-body)" }}
    >
      {children}
    </div>
  );
}
