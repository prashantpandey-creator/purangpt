<div align="center">

# 🪔 PuranGPT Growth Engine

### *Make the app money on autopilot — pure online, no calls, no faces.*

**An autonomous marketing machine that writes, designs, and posts your content
everywhere automation is allowed — and queues the rest for a one-click yes.**

</div>

---

## 🎯 What this is, in one breath

You wanted PuranGPT to earn on its own — *"without seeing anyone's face or talking
to a customer, pure online."* This is that machine.

It takes your social accounts and API keys, **generates the marketing**
(post copy, images, eventually faceless voiceover videos), and **posts it
automatically** to every channel that allows automation. For the risky channels
that ban bots (Reddit, app-store reviews), it writes the perfect post and **waits
for you to tap "approve."** That human-in-the-loop isn't a gap — it's what keeps
your accounts from getting banned.

It's built **multi-tenant from day one**: PuranGPT is customer #1, but every future
app you build plugs into the same engine. One day it becomes a product you sell.

> **Important boundary (so you trust it):** this engine lives in its OWN folder
> (`growth_engine/`) and its OWN database tables (all prefixed `ge_`). It does
> **not** touch your chat brain, your prompts, your RAG search, or your frontend.
> It *borrows* your existing LLM router and your encryption — it never reinvents or
> modifies them. Your working app stays exactly as it is.

---

## 💰 How it actually makes money

```
        ┌─────────────────────────────────────────────────────────┐
        │  1. You connect an account once (X, Telegram, …)         │
        │     → keys get encrypted and locked in the vault         │
        └────────────────────────────┬────────────────────────────┘
                                      │
        ┌────────────────────────────▼────────────────────────────┐
        │  2. The engine WRITES a daily post (a Gita verse, on     │
        │     brand, in your voice) using your own LLM router      │
        └────────────────────────────┬────────────────────────────┘
                                      │
        ┌────────────────────────────▼────────────────────────────┐
        │  3. It CHECKS the post (length, hashtags, banned words)  │
        │     BEFORE anything touches a live API                   │
        └────────────────────────────┬────────────────────────────┘
                                      │
              auto channel? ──────────┼────────── risky channel?
                    │                                    │
        ┌───────────▼───────────┐          ┌─────────────▼────────────┐
        │ 4a. POSTS IT NOW       │          │ 4b. QUEUES it for your    │
        │     → real live URL    │          │     1-click approval      │
        └───────────┬───────────┘          └─────────────┬────────────┘
                    │                                     │
        ┌───────────▼─────────────────────────────────────▼──────────┐
        │  5. Logs the result, tracks reach → more eyes → more users  │
        │     → more subscriptions. On repeat. Forever. Hands-off.    │
        └─────────────────────────────────────────────────────────────┘
```

**More eyes on the app → more sign-ups → more Pro subscriptions.** The engine is the
top of that funnel, running itself.

---

## 🧠 The two halves of the brain

The engine is deliberately split so a marketing job can never slow down or crash
your chat app.

| Half | File | What it does | Runs where |
|------|------|--------------|------------|
| **The Dashboard** | `app.py` | The control panel API. Connect accounts, create campaigns, approve/reject queued posts, see analytics. | FastAPI on port `8100` |
| **The Worker** | `worker.py` | The tireless robot. Wakes on a timer, asks "what's due?", writes the post, checks it, publishes it, logs it. | A separate background process |

Keeping them apart means the worker can spend 30 seconds rendering a video without
your dashboard (or your chat app) ever freezing.

---

## 🔌 Channels: "auto" vs "draft"

Every channel is a small plug-in file. Adding a new one = one new file + one line.
Each declares a **mode**:

- **`auto`** — the engine posts on its own. *(X/Twitter, Telegram are live today.)*
- **`draft`** — the engine writes it, but a human must approve before it posts.
  *(Reddit, reviews — channels that ban bots and would get you blacklisted.)*

```
connectors/
  base.py        ← the contract every channel must follow
  registry.py    ← the phone book of all channels
  x_twitter.py   ← LIVE (auto)
  telegram.py    ← LIVE (auto)
  …              ← youtube, instagram, reddit(draft), … plug in here
```

---

## 🛡️ Why it's safe (the parts that protect you)

These aren't nice-to-haves — they're the difference between "passive income" and
"banned accounts + leaked keys."

1. **Your keys are encrypted at rest.** API secrets go through Fernet encryption
   (your existing `encrypt_keys`). The database only ever holds ciphertext — we
   verified that plaintext like `CK123` never appears in the stored column. Keys
   are decrypted *only* in memory, at the moment of posting.

2. **Nothing posts without passing the gate.** Every post is checked for length,
   hashtag count, and banned promotional terms *before* it reaches a live API. A
   300-character post can't sneak onto Twitter's 280-char limit — it's rejected and
   discarded.

3. **It can't double-post.** Each scheduled slot gets a stable "dedup key." If the
   worker restarts and replays a tick, the database's UNIQUE constraint silently
   blocks the duplicate. Your followers never see the same verse twice in a row.

4. **It never crashes on a bad key.** A failed post retries with backoff, then marks
   itself `failed` and moves on. The worker keeps running.

---

## 🗄️ The data (6 new tables, all `ge_` prefixed)

All live in a local Postgres for development, sharing nothing with your chat data
except the connection. Created automatically, idempotently — run it twice, no harm.

| Table | Holds |
|-------|-------|
| `ge_campaigns` | A marketing campaign: which app, goal, audience, channels, cadence |
| `ge_content_assets` | Generated pieces: copy, images, video, blog posts |
| `ge_channel_connections` | **Your encrypted account keys** (one per channel) |
| `ge_post_queue` | What's scheduled / pending approval / posted |
| `ge_post_log` | Proof of every post: the real live URL, success or failure |
| `ge_analytics` | Reach/engagement metrics pulled back from each channel |

---

## 🏗️ The "don't reinvent" principle

This engine is fast to build and safe *because* it reuses what already works in
your backend, through thin adapter files that just re-export — they add no new
logic:

| Adapter | Borrows from your backend | Why |
|---------|---------------------------|-----|
| `llm.py` | The generic, key-driven LLM router with failover | Same brains that power chat write the posts |
| `vault.py` | Fernet `encrypt_keys` / `decrypt_keys` | Same proven encryption guards the API keys |
| `db.py` | The pooled Postgres connection | No new connection pool; reuses one that works |

> One real gotcha we already solved: the LLM router needs an HTTP session that
> normally only exists inside the web server. For the standalone worker we added
> `ensure_http_client()` to spin one up — so the robot can think outside the app.

---

## ✅ What's built and proven today

- ✅ **Content generation works end-to-end** — produced a real, on-brand, 271-char
  Bhagavad Gita 2.47 post that passed every safety check, using your own LLM.
- ✅ **The vault works** — keys encrypt in, decrypt out, ciphertext-only in the DB.
- ✅ **All 6 tables** create cleanly and idempotently.
- ✅ **The worker + dashboard** are written, compile clean, and wire the whole loop.
- ✅ **Four safety tools** (post-check, brief-check, scheduler, response-normalizer)
  — each independently tested against real captured API responses.

## 🚧 What's next

- ⏭️ A dashboard screen in the app to connect accounts with one click.
- ⏭️ **Your real X + Telegram keys** → the first fully-automatic live post.
- ⏭️ Faceless verse videos (images + voiceover) auto-uploaded to YouTube/Instagram.
- ⏭️ More channels, then spin the engine out as its own standalone product.

---

<div align="center">

*Built as a sidecar to PuranGPT. Touches nothing that already works.*
*One verse at a time, posting itself, while you sleep.* 🌙

</div>
