#!/usr/bin/env node
/**
 * setup-stripe.mjs — one-shot, idempotent Stripe configuration for PuranGPT.
 *
 * Does EVERYTHING via the Stripe API so there are no manual dashboard steps:
 *   1. Creates (or reuses) the "PuranGPT Pro" product
 *   2. Creates (or reuses) the monthly + annual recurring prices
 *   3. Registers the webhook endpoint at /api/billing/stripe/webhook
 *   4. Enables the Customer Billing Portal with cancellation + plan management
 *
 * It NEVER deletes anything and is safe to run repeatedly. On each run it prints
 * the env-var lines you (or CI) should set:
 *   STRIPE_PRO_MONTHLY_PRICE_ID, STRIPE_PRO_ANNUAL_PRICE_ID, STRIPE_WEBHOOK_SECRET
 *
 * Usage:
 *   STRIPE_SECRET_KEY=sk_live_xxx node scripts/setup-stripe.mjs
 *   # optional overrides:
 *   SITE_URL=https://purangpt.com  MONTHLY_USD=11.11  ANNUAL_USD=92.59
 */

import Stripe from "stripe";

const KEY = process.env.STRIPE_SECRET_KEY;
if (!KEY) {
  console.error("✗ STRIPE_SECRET_KEY is required.\n  Run: STRIPE_SECRET_KEY=sk_live_xxx node scripts/setup-stripe.mjs");
  process.exit(1);
}
const LIVE = KEY.startsWith("sk_live_");
const SITE_URL    = process.env.SITE_URL    || "https://purangpt.com";
const MONTHLY_USD = Number(process.env.MONTHLY_USD || "11.11");
const ANNUAL_USD  = Number(process.env.ANNUAL_USD  || "92.59");
const WEBHOOK_URL = `${SITE_URL}/api/billing/stripe/webhook`;

const stripe = new Stripe(KEY);
const usd = (n) => Math.round(n * 100); // dollars → cents

console.log(`\n=== PuranGPT Stripe setup (${LIVE ? "LIVE" : "TEST"} mode) ===`);
console.log(`Site: ${SITE_URL}\n`);

const out = {};

// ── 1. Product ───────────────────────────────────────────────────────────────
async function ensureProduct() {
  const existing = await stripe.products.search({
    query: `active:'true' AND metadata['purangpt_key']:'pro'`,
  });
  if (existing.data.length) {
    console.log(`✓ Product exists: ${existing.data[0].id}`);
    return existing.data[0];
  }
  const p = await stripe.products.create({
    name: "PuranGPT Pro",
    description: "Unlimited questions, Deep Research, priority responses, API access.",
    metadata: { purangpt_key: "pro" },
  });
  console.log(`+ Created product: ${p.id}`);
  return p;
}

// ── 2. Prices (recurring) ─────────────────────────────────────────────────────
async function ensurePrice(productId, interval, amountCents, lookupKey) {
  const existing = await stripe.prices.list({ product: productId, active: true, limit: 100 });
  const match = existing.data.find(
    (pr) => pr.recurring?.interval === interval && pr.unit_amount === amountCents && pr.currency === "usd",
  );
  if (match) {
    console.log(`✓ ${interval} price exists: ${match.id} ($${(amountCents / 100).toFixed(2)})`);
    return match;
  }
  const pr = await stripe.prices.create({
    product: productId,
    currency: "usd",
    unit_amount: amountCents,
    recurring: { interval },
    lookup_key: lookupKey,
    tax_behavior: "inclusive",
  });
  console.log(`+ Created ${interval} price: ${pr.id} ($${(amountCents / 100).toFixed(2)})`);
  return pr;
}

// ── 3. Webhook endpoint ───────────────────────────────────────────────────────
const WEBHOOK_EVENTS = [
  "checkout.session.completed",
  "customer.subscription.updated",
  "customer.subscription.deleted",
  "invoice.payment_failed",
];
async function ensureWebhook() {
  const all = await stripe.webhookEndpoints.list({ limit: 100 });
  const existing = all.data.find((w) => w.url === WEBHOOK_URL);
  if (existing) {
    // Make sure it listens for all the events we need.
    await stripe.webhookEndpoints.update(existing.id, { enabled_events: WEBHOOK_EVENTS });
    console.log(`✓ Webhook exists & updated: ${existing.id} → ${WEBHOOK_URL}`);
    console.log(`  (secret not re-shown by Stripe for existing endpoints — keep your current STRIPE_WEBHOOK_SECRET)`);
    return existing;
  }
  const w = await stripe.webhookEndpoints.create({
    url: WEBHOOK_URL,
    enabled_events: WEBHOOK_EVENTS,
  });
  console.log(`+ Created webhook: ${w.id} → ${WEBHOOK_URL}`);
  out.STRIPE_WEBHOOK_SECRET = w.secret; // only returned on create
  return w;
}

// ── 4. Customer portal ────────────────────────────────────────────────────────
async function ensurePortal(productId, monthlyId, annualId) {
  const cfg = await stripe.billingPortal.configurations.create({
    business_profile: {
      headline: "Manage your PuranGPT Pro subscription",
    },
    default_return_url: `${SITE_URL}/settings`,
    features: {
      customer_update: { enabled: true, allowed_updates: ["email"] },
      invoice_history: { enabled: true },
      payment_method_update: { enabled: true },
      subscription_cancel: {
        enabled: true,
        mode: "at_period_end",
        cancellation_reason: { enabled: true, options: ["too_expensive", "missing_features", "switched_service", "unused", "other"] },
      },
      subscription_update: {
        enabled: true,
        default_allowed_updates: ["price"],
        products: [{ product: productId, prices: [monthlyId, annualId] }],
      },
    },
  });
  console.log(`+ Portal configuration created & set as default: ${cfg.id}`);
  return cfg;
}

// ── Run ───────────────────────────────────────────────────────────────────────
try {
  const product = await ensureProduct();
  const monthly = await ensurePrice(product.id, "month", usd(MONTHLY_USD), "purangpt_pro_monthly");
  const annual  = await ensurePrice(product.id, "year",  usd(ANNUAL_USD),  "purangpt_pro_annual");
  await ensureWebhook();
  await ensurePortal(product.id, monthly.id, annual.id);

  out.STRIPE_PRO_MONTHLY_PRICE_ID = monthly.id;
  out.STRIPE_PRO_ANNUAL_PRICE_ID  = annual.id;

  console.log(`\n=== DONE. Set these as GitHub Secrets / container env: ===`);
  for (const [k, v] of Object.entries(out)) console.log(`${k}=${v}`);
  if (!out.STRIPE_WEBHOOK_SECRET) {
    console.log(`# (STRIPE_WEBHOOK_SECRET unchanged — existing webhook kept its secret)`);
  }
  console.log(`\nGitHub one-liner (run from repo root):`);
  for (const [k, v] of Object.entries(out)) console.log(`  gh secret set ${k} --body "${v}"`);
  console.log("");
} catch (e) {
  console.error("✗ Stripe setup failed:", e.message);
  process.exit(1);
}
