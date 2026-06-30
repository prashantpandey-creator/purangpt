import { type NextRequest, NextResponse } from 'next/server';
import Stripe from 'stripe';
import { parseGoogleSession, parseLogtoSession } from '@/lib/session';
import { getSubscription } from '@/lib/db';

export const runtime = 'nodejs';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY || 'sk_test_placeholder');

export async function POST(request: NextRequest): Promise<Response> {
  const googleCookie = request.cookies.get('purangpt_session')?.value;
  const logtoCookie  = request.cookies.get('logto_session')?.value;
  const user =
    (googleCookie ? await parseGoogleSession(googleCookie) : null) ??
    (logtoCookie  ? await parseLogtoSession(logtoCookie)   : null);

  if (!user) return NextResponse.json({ error: 'Unauthenticated' }, { status: 401 });

  const sub = await getSubscription(user.sub);
  if (!sub || sub.provider !== 'stripe') {
    return NextResponse.json({ error: 'No Stripe subscription found' }, { status: 404 });
  }

  // Retrieve the Stripe customer ID from the subscription
  let customerId: string | null = null;
  if (sub.external_subscription_id) {
    try {
      const stripeSub = await stripe.subscriptions.retrieve(sub.external_subscription_id);
      customerId = typeof stripeSub.customer === 'string' ? stripeSub.customer : stripeSub.customer.id;
    } catch { /* fall through */ }
  }

  if (!customerId) {
    return NextResponse.json({ error: 'Could not locate Stripe customer' }, { status: 404 });
  }

  const { origin } = new URL(request.url);
  const session = await stripe.billingPortal.sessions.create({
    customer: customerId,
    return_url: `${origin}/settings`,
  });

  return NextResponse.json({ url: session.url });
}
