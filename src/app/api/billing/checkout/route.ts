import { type NextRequest, NextResponse } from 'next/server';
import { parseGoogleSession, parseLogtoSession } from '@/lib/session';
import Stripe from 'stripe';

export const runtime = 'nodejs';

const RAZORPAY_KEY_ID     = process.env.RAZORPAY_KEY_ID     || process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID || '';
const RAZORPAY_KEY_SECRET = process.env.RAZORPAY_KEY_SECRET || '';
const STRIPE_SECRET_KEY   = process.env.STRIPE_SECRET_KEY   || '';

// Pre-created Stripe Price IDs (tax-inclusive, $11.11/mo shown to customer)
const STRIPE_PRO_MONTHLY_PRICE_ID = process.env.STRIPE_PRO_MONTHLY_PRICE_ID || '';
const STRIPE_PRO_ANNUAL_PRICE_ID  = process.env.STRIPE_PRO_ANNUAL_PRICE_ID  || '';

// Use dummy key if undefined just to prevent crash on init; it will error on actual checkout if invalid
const stripe = new Stripe(STRIPE_SECRET_KEY || 'sk_test_placeholder');

const PLANS: Record<string, { monthly_inr: number; annual_inr: number; name: string }> = {
  pro: {
    name: 'PuranGPT Pro',
    monthly_inr: 29900,  // ₹299 in paise
    annual_inr:  249900, // ₹2499 in paise
  },
};

/**
 * POST /api/billing/checkout
 * Creates a Razorpay order OR a Stripe Checkout Session for the chosen plan.
 * Returns { id, amount, currency, key_id, url? } to the client.
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

  let body: { plan?: string; provider?: 'stripe' | 'razorpay'; billing_cycle?: 'monthly' | 'annual'; success_url?: string; cancel_url?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const provider = body.provider || 'razorpay';
  const planKey = (body.plan ?? 'pro').toLowerCase();
  const plan = PLANS[planKey];
  if (!plan) {
    return NextResponse.json({ error: 'Unknown plan' }, { status: 400 });
  }

  const billingCycle = body.billing_cycle ?? 'monthly';

  // ── STRIPE FLOW ────────────────────────────────────────────────────────────
  if (provider === 'stripe') {
    if (!STRIPE_SECRET_KEY) {
      return NextResponse.json({ error: 'Stripe is not configured on the server.' }, { status: 503 });
    }

    // Use pre-created Price IDs (tax-inclusive, $11.11/mo or $92.59/yr shown to customer).
    // Falls back to price lookup by plan if env vars not set.
    const priceId = billingCycle === 'annual' ? STRIPE_PRO_ANNUAL_PRICE_ID : STRIPE_PRO_MONTHLY_PRICE_ID;
    if (!priceId) {
      return NextResponse.json({ error: 'Stripe price not configured for this plan.' }, { status: 503 });
    }

    try {
      const session = await stripe.checkout.sessions.create({
        payment_method_types: ['card'],
        customer_email: user.email,
        line_items: [{ price: priceId, quantity: 1 }],
        mode: 'subscription',
        success_url: body.success_url || `${request.nextUrl.origin}/pricing?success=true`,
        cancel_url:  body.cancel_url  || `${request.nextUrl.origin}/pricing?cancel=true`,
        client_reference_id: user.sub,
        metadata: {
          user_sub: user.sub,
          plan: planKey,
        },
      });

      return NextResponse.json({ url: session.url });
    } catch (err: any) {
      console.error('[billing/checkout] Stripe session creation failed:', err);
      return NextResponse.json({ error: err.message || 'Payment gateway error' }, { status: 502 });
    }
  }

  // ── RAZORPAY FLOW ──────────────────────────────────────────────────────────
  if (!RAZORPAY_KEY_ID || !RAZORPAY_KEY_SECRET) {
    return NextResponse.json({ error: 'Razorpay is not configured on the server.' }, { status: 503 });
  }

  const amount = billingCycle === 'annual' ? plan.annual_inr : plan.monthly_inr;
  const auth = Buffer.from(`${RAZORPAY_KEY_ID}:${RAZORPAY_KEY_SECRET}`).toString('base64');
  
  const orderRes = await fetch('https://api.razorpay.com/v1/orders', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Basic ${auth}`,
    },
    body: JSON.stringify({
      amount,
      currency: 'INR',
      receipt: `purangpt_${user.sub.slice(0, 16)}_${Date.now()}`,
      notes: {
        user_sub:      user.sub,
        user_email:    user.email,
        plan:          planKey,
        billing_cycle: billingCycle,
      },
    }),
  });

  if (!orderRes.ok) {
    const err = await orderRes.text();
    console.error('[billing/checkout] Razorpay order creation failed:', err);
    return NextResponse.json({ error: 'Payment gateway error' }, { status: 502 });
  }

  const order = await orderRes.json();

  return NextResponse.json({
    id:       order.id,
    amount:   order.amount,
    currency: order.currency,
    key_id:   RAZORPAY_KEY_ID,
    plan:     planKey,
    name:     plan.name,
  });
}
