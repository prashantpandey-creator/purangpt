import { type NextRequest, NextResponse } from 'next/server';
import { upsertSubscription, updateSubscription, recordPayment, syncProfileRole } from '@/lib/db';

export const runtime = 'nodejs';

const RAZORPAY_WEBHOOK_SECRET = process.env.RAZORPAY_WEBHOOK_SECRET || '';

/**
 * POST /api/billing/webhook
 * Receives Razorpay webhook events. Verifies the X-Razorpay-Signature
 * header using HMAC-SHA256 before processing any event.
 *
 * Idempotency: every event write uses the Razorpay event ID as a unique
 * key — a retried delivery silently returns 200 without double-processing.
 *
 * Handles:
 *   subscription.activated   → plan = 'pro', status = 'active'
 *   subscription.charged     → extend current_period_end
 *   payment.failed           → status = 'past_due' (grace period, no downgrade)
 *   subscription.cancelled   → status = 'canceled' (Pro until period end)
 */
export async function POST(request: NextRequest): Promise<Response> {
  const rawBody = await request.text();
  const signature = request.headers.get('x-razorpay-signature') ?? '';

  // FAIL CLOSED. An unverifiable webhook must be REJECTED, never trusted — this
  // endpoint grants Pro from a user_sub in the (attacker-controllable) body, so a
  // skipped signature check is a free-Pro-for-anyone hole. If the secret is
  // missing/placeholder the request cannot be authenticated, so we 503 rather
  // than process it. A genuinely misconfigured deploy fails loudly (correct);
  // legitimate Razorpay calls carry a valid signature and pass.
  if (!RAZORPAY_WEBHOOK_SECRET || RAZORPAY_WEBHOOK_SECRET === 'no_secret') {
    console.error('[webhook] RAZORPAY_WEBHOOK_SECRET not configured — rejecting (fail-closed)');
    return NextResponse.json(
      { error: 'Webhook verification unavailable' },
      { status: 503 },
    );
  }
  const expected = await hmacSha256(rawBody, RAZORPAY_WEBHOOK_SECRET);
  if (!timingSafeEqualHex(expected, signature)) {
    console.warn('[webhook] Invalid signature');
    return NextResponse.json({ error: 'Invalid signature' }, { status: 400 });
  }

  let event: {
    event: string;
    payload: {
      subscription?: { entity?: Record<string, unknown> };
      payment?: { entity?: Record<string, unknown> };
    };
  };

  try {
    event = JSON.parse(rawBody);
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  // Extract user_sub from subscription/payment notes
  const subEntity = event.payload?.subscription?.entity ?? {};
  const payEntity = event.payload?.payment?.entity ?? {};
  const notes = (subEntity.notes ?? payEntity.notes ?? {}) as Record<string, string>;
  const userSub = notes.user_sub;

  if (!userSub) {
    // We can't link this event to a user — log and ack
    console.warn('[webhook] Event missing user_sub in notes:', event.event);
    return NextResponse.json({ ok: true });
  }

  // Idempotency key: Razorpay includes an event ID in the webhook.
  // Fall back to a composite if absent.
  const eventId = (event as any).id ?? `${event.event}_${Date.now()}`;

  // Record event (returns false if duplicate)
  const isNew = await recordPayment({
    user_sub:          userSub,
    razorpay_event_id: eventId,
    event_type:        event.event,
    payload:           event,
  });

  if (!isNew) {
    // Already processed — safe to ack
    return NextResponse.json({ ok: true, duplicate: true });
  }

  // Process the event
  switch (event.event) {
    case 'subscription.activated': {
      const endMs = subEntity.current_end ? (subEntity.current_end as number) * 1000 : null;
      const periodEnd = endMs ? new Date(endMs) : null;
      await upsertSubscription(userSub, {
        plan:                     'pro',
        status:                   'active',
        current_period_end:       periodEnd?.toISOString() ?? null,
        external_subscription_id: subEntity.id as string | undefined,
        provider:                 'razorpay',
      });
      await syncProfileRole(userSub, 'pro', periodEnd);
      break;
    }

    case 'subscription.charged': {
      const endMs = subEntity.current_end ? (subEntity.current_end as number) * 1000 : null;
      const periodEnd = endMs ? new Date(endMs) : null;
      await updateSubscription(userSub, {
        plan:               'pro',
        status:             'active',
        current_period_end: periodEnd?.toISOString() ?? null,
      });
      await syncProfileRole(userSub, 'pro', periodEnd);
      break;
    }

    case 'payment.failed': {
      // Grace period — mark as past_due but do NOT downgrade plan yet.
      await updateSubscription(userSub, { status: 'past_due' });
      break;
    }

    case 'subscription.cancelled': {
      // Retain Pro access until current_period_end; only update status.
      await updateSubscription(userSub, { status: 'canceled' });
      break;
    }

    default:
      // Unhandled event types are silently acknowledged
      break;
  }

  return NextResponse.json({ ok: true });
}

async function hmacSha256(message: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(message));
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Constant-time hex-string comparison. A plain `!==` short-circuits on the first
 * differing byte, leaking how much of a guessed signature is correct via timing.
 * This compares every character regardless, so the duration is independent of
 * where (or whether) the strings differ.
 */
function timingSafeEqualHex(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}
