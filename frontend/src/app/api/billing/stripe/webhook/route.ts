import { type NextRequest, NextResponse } from 'next/server';
import Stripe from 'stripe';
import { upsertSubscription, recordPayment, syncProfileRole } from '@/lib/db';

export const runtime = 'nodejs';

const STRIPE_SECRET_KEY = process.env.STRIPE_SECRET_KEY || '';
const STRIPE_WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET || '';

const stripe = new Stripe(STRIPE_SECRET_KEY || 'sk_test_placeholder');

export async function POST(request: NextRequest): Promise<Response> {
  const body = await request.text();
  const signature = request.headers.get('stripe-signature');

  if (!signature) {
    return NextResponse.json({ error: 'Missing stripe-signature header' }, { status: 400 });
  }

  let event: Stripe.Event;

  try {
    event = stripe.webhooks.constructEvent(body, signature, STRIPE_WEBHOOK_SECRET);
  } catch (err: any) {
    console.error('[stripe/webhook] Signature verification failed:', err.message);
    return NextResponse.json({ error: `Webhook Error: ${err.message}` }, { status: 400 });
  }

  try {
    switch (event.type) {
      case 'checkout.session.completed': {
        const session = event.data.object as Stripe.Checkout.Session;

        const userSub = session.client_reference_id || session.metadata?.user_sub;
        const planKey = session.metadata?.plan || 'pro';
        if (!userSub) {
          console.error('[stripe/webhook] Missing user_sub in session metadata');
          break;
        }

        const subscriptionId = typeof session.subscription === 'string' ? session.subscription : null;

        // Fetch period end from the Stripe subscription object
        let periodEnd: Date | null = null;
        if (subscriptionId) {
          const sub = await stripe.subscriptions.retrieve(subscriptionId);
          periodEnd = new Date((sub as any).current_period_end * 1000);
        }

        await upsertSubscription(userSub, {
          plan: planKey,
          status: 'active',
          external_subscription_id: subscriptionId || session.id,
          provider: 'stripe',
          current_period_end: periodEnd?.toISOString() ?? null,
        });

        // Sync role to backend profiles table so rate limits apply immediately
        await syncProfileRole(userSub, planKey, periodEnd);

        await recordPayment({
          user_sub: userSub,
          razorpay_event_id: event.id,
          event_type: event.type,
          payload: session,
        });
        console.log(`[stripe/webhook] Activated ${planKey} for ${userSub}, period ends ${periodEnd}`);
        break;
      }

      case 'customer.subscription.updated': {
        const subscription = event.data.object as Stripe.Subscription;
        // Map Stripe statuses to our statuses
        const statusMap: Record<string, string> = {
          active: 'active',
          past_due: 'past_due',
          canceled: 'canceled',
          unpaid: 'past_due',
          trialing: 'active',
        };
        const status = statusMap[subscription.status] ?? subscription.status;
        const periodEnd = new Date((subscription as any).current_period_end * 1000);
        // Don't cut a paying user off early: only drop to 'free' once the paid
        // period has actually elapsed. While it's canceled-but-not-yet-expired we
        // keep them on 'pro' with the period end recorded — the backend's
        // effective-role expiry (get_profile) downgrades them exactly at periodEnd.
        const expired = periodEnd.getTime() <= Date.now();
        const plan = status === 'canceled' && expired ? 'free' : 'pro';

        // Look up user_sub from external_subscription_id
        const { sql } = await import('@/lib/db');
        if (sql) {
          const rows = await sql`
            SELECT user_sub FROM subscriptions
            WHERE external_subscription_id = ${subscription.id} LIMIT 1
          `;
          if (rows.length > 0) {
            const userSub = rows[0].user_sub as string;
            await upsertSubscription(userSub, { plan, status, current_period_end: periodEnd.toISOString() });
            await syncProfileRole(userSub, plan, plan === 'free' ? null : periodEnd);
            console.log(`[stripe/webhook] subscription.updated: ${userSub} → ${plan}/${status} (period ends ${periodEnd.toISOString()})`);
          }
        }
        break;
      }

      case 'customer.subscription.deleted': {
        const subscription = event.data.object as Stripe.Subscription;
        const { sql } = await import('@/lib/db');
        if (sql) {
          const rows = await sql`
            SELECT user_sub FROM subscriptions
            WHERE external_subscription_id = ${subscription.id} LIMIT 1
          `;
          if (rows.length > 0) {
            const userSub = rows[0].user_sub as string;
            await upsertSubscription(userSub, { plan: 'free', status: 'canceled', current_period_end: null });
            await syncProfileRole(userSub, 'free', null);
            console.log(`[stripe/webhook] subscription.deleted: ${userSub} downgraded to free`);
          }
        }
        break;
      }

      default:
        break;
    }

    return NextResponse.json({ received: true });
  } catch (err: any) {
    console.error('[stripe/webhook] Error processing event:', err);
    return NextResponse.json({ error: 'Internal Server Error' }, { status: 500 });
  }
}
