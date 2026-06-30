// ─────────────────────────────────────────────────────────────────────────
//  shotChat — boot a seeded conversation in the real app and screenshot it,
//  so chat rendering (card vs floating-on-void, streaming, layout) can be
//  verified against actual pixels. Dev-only. Requires `next dev` on :3000 and
//  CHROME_BIN pointing at a chrome-headless-shell binary.
// ─────────────────────────────────────────────────────────────────────────

import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const OUT = join(__dirname, "..", "scratch", "page-shots");
const BASE = process.env.BASE_URL || "http://localhost:3000";

// A settled assistant answer with markdown structure + a citation marker, so the
// screenshot shows exactly how an answer renders on the field.
const SESSION = "shot-session-1";
const ASSISTANT = `## Summary

The **Bhagavad Gītā** (2.47) teaches *karma-yoga* — action without attachment to its fruits. One acts as an offering, steady in success and failure alike.

### Extracted Sacred Text

> कर्मण्येवाधिकारस्ते मा फलेषु कदाचन ।

You have a right to action alone, never to its fruits [1].

### Explanation

This is the heart of *niṣkāma karma*: duty performed as worship, the mind resting in equanimity rather than craving outcome.`;

const conv = {
  id: "shot-conv-1",
  title: "What does the Gita say about karma?",
  sessionId: SESSION,
  createdAt: 1750000000000,
  updatedAt: 1750000000000,
  messages: [
    { id: "u1", role: "user", content: "What does the Gita say about karma?", timestamp: 1750000000000 },
    { id: "a1", role: "assistant", content: ASSISTANT, timestamp: 1750000000001,
      sources: [{ id: "1", text: "Bhagavad Gita 2.47", source: "Bhagavad Gita", reference: "2.47" }] },
  ],
};

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: process.env.CHROME_BIN || undefined,
    args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--no-sandbox"],
  });
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1.5 });
  page.on("pageerror", (e) => console.log("  [pageerror]", String(e).slice(0, 200)));

  // Visit once to get the origin, seed localStorage, then load the seeded chat.
  await page.goto(BASE + "/chat", { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.evaluate(({ conv }) => {
    localStorage.setItem("purangpt:conversations", JSON.stringify([conv]));
    localStorage.setItem("purangpt:activeConversation", JSON.stringify(conv.id));
  }, { conv });

  await page.goto(`${BASE}/chat?session=${SESSION}`, { waitUntil: "networkidle", timeout: 60000 });
  // Give the field + answer-manifest rise animation a moment to settle.
  await page.waitForTimeout(2500);

  const deskFull = join(OUT, "chat-desktop.png");
  await page.screenshot({ path: deskFull });
  console.log("✓ desktop full →", deskFull);

  // Mobile viewport too (the user often tests on phone).
  const m = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 });
  await m.goto(BASE + "/chat", { waitUntil: "domcontentloaded", timeout: 60000 });
  await m.evaluate(({ conv }) => {
    localStorage.setItem("purangpt:conversations", JSON.stringify([conv]));
    localStorage.setItem("purangpt:activeConversation", JSON.stringify(conv.id));
  }, { conv });
  await m.goto(`${BASE}/chat?session=${SESSION}`, { waitUntil: "networkidle", timeout: 60000 });
  await m.waitForTimeout(2500);
  const mob = join(OUT, "chat-mobile.png");
  await m.screenshot({ path: mob });
  console.log("✓ mobile →", mob);

  // Also dump the computed background/border of the answer wrapper to settle
  // the "is it a card?" question definitively.
  const probe = await page.evaluate(() => {
    const el = document.querySelector(".answer-manifest");
    if (!el) return { found: false };
    const cs = getComputedStyle(el);
    const parent = el.parentElement ? getComputedStyle(el.parentElement) : null;
    return {
      found: true,
      manifest: { background: cs.backgroundColor, border: cs.borderTopWidth + " " + cs.borderTopStyle, boxShadow: cs.boxShadow },
      parent: parent ? { background: parent.backgroundColor, border: parent.borderTopWidth, boxShadow: parent.boxShadow } : null,
    };
  });
  console.log("answer-manifest computed style:", JSON.stringify(probe, null, 2));

  await browser.close();
}
main().catch((e) => { console.error(e); process.exit(1); });
