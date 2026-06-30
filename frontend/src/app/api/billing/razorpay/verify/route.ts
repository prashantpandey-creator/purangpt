import { type NextRequest, NextResponse } from 'next/server';
import { timingSafeEqual } from 'crypto';
import { parseGoogleSession, parseLogtoSession } from '@/lib/session';
import { upsertSubscription, recordPayment, syncProfileRole } from '@/lib/db';

export const runtime = 'nodejs';

const RAZORPAY_KEY_SECRET = process.env.RAZORPAY_KEY_SECRET || '';

/** Constant-time hex-string comparison (avoids an HMAC timing side-channel). */
function safeEqualHex(a: string, b: string): boolean {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  try {
    return timingSafeEqual(Buffer.from(a, 'utf8'), Buffer.from(b, 'utf8'));
  } catch {
    return false;
  }
}

/**
 * POST /api/billing/razorpay/verify
 * Called by the Razorpay SDK handler after a successful payment.
 * Verifies the HMAC signature and upgrades the user's plan.
 *
 * NOTE: This endpoint verifies the payment signature before granting Pro.
 * A user cannot fake this without the Razorpay key secret.
 */
export async function POST(request: NextRequest): Promise<Response> {
  const googleCookie = request.cookies.get('purangpt_session')?.value;
  const logtoCookie  = request.cookies.get('logto_session')?.value;

  const user =
    (googleCookie ? await parseGoogleSession(googleCookie) : null) ??
    (logtoCookie  ? await parseLogtoSession(logtoCookie)   : null);

  if (!user) {
    return NextResponse.json({ error: 'Unauthenticated' }, { status: 401 });
  }

  let body: {
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
    plan?: string;
    billing_cycle?: string;
  };

  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const { razorpay_order_id, razorpay_payment_id, razorpay_signature } = body;

  if (!razorpay_order_id || !razorpay_payment_id || !razorpay_signature) {
    return NextResponse.json({ error: 'Missing payment fields' }, { status: 400 });
  }

  // Verify HMAC-SHA256 signature
  const expectedSignature = await hmacSha256(
    `${razorpay_order_id}|${razorpay_payment_id}`,
    RAZORPAY_KEY_SECRET
  );

  if (!safeEqualHex(expectedSignature, razorpay_signature)) {
    console.warn('[billing/verify] Signature mismatch for user', user.sub);
    return NextResponse.json({ error: 'Invalid payment signature' }, { status: 400 });
  }

  // Calculate period end (30 days for monthly, 365 for annual)
  const billingCycle = body.billing_cycle ?? 'monthly';
  const days = billingCycle === 'annual' ? 365 : 30;
  const periodEndDate = new Date(Date.now() + days * 24 * 60 * 60 * 1000);

  try {
    // Grant access FIRST (both writes must succeed), then log the payment. If a
    // write throws we return 500 without having marked the payment processed, so
    // the client/retry can re-run and the user is never left paid-but-not-granted.
    await upsertSubscription(user.sub, {
      plan:                     'pro',
      status:                   'active',
      current_period_end:       periodEndDate.toISOString(),
      external_subscription_id: razorpay_order_id,
      provider:                 'razorpay',
    });

    // Sync role to backend profiles table so FastAPI rate limits apply immediately.
    // syncProfileRole throws on failure — let it surface as a 500.
    await syncProfileRole(user.sub, 'pro', periodEndDate);

    // Idempotency log last (unique on razorpay_payment_id).
    await recordPayment({
      user_sub:          user.sub,
      razorpay_event_id: razorpay_payment_id,
      event_type:        'payment.captured',
      payload:           body,
    });
  } catch (err) {
    console.error('[billing/verify] Failed to grant Pro after verified payment:', err);
    return NextResponse.json({ error: 'Failed to activate subscription' }, { status: 500 });
  }

  return NextResponse.json({ ok: true, plan: 'pro' });
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
