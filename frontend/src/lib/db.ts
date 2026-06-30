import postgres from 'postgres';

/**
 * Frontend DB (logto-db/logto): stores subscriptions, payments, community data.
 * Backend DB (pgvector/purangpt): stores profiles with role field that the FastAPI
 * rate-limiter reads. Both are separate Postgres containers on the same Hetzner box.
 */
const sql = process.env.DATABASE_URL
  ? postgres(process.env.DATABASE_URL, { max: 5, idle_timeout: 20 })
  : null;

// Backend profiles DB — used only to sync role after payment so the FastAPI
// rate-limiter (which reads profiles.role) sees the correct plan immediately.
const backendSql = process.env.VECTOR_DB_URL
  ? postgres(process.env.VECTOR_DB_URL, { max: 2, idle_timeout: 20 })
  : null;

// Shared client so other modules (e.g. community.ts) reuse the same pool.
export { sql };

/**
 * Server-side Pro check — mirrors SubscriptionContext on the web
 * (["pro","scholar","admin"] count as Pro). Kept here so API routes and the
 * key-authed endpoint share one source of truth.
 */
export function isProPlan(plan?: string | null): boolean {
  return ['pro', 'scholar', 'admin'].includes((plan ?? 'free').toLowerCase());
}

export interface Subscription {
  plan: string;
  status: string;
  current_period_end?: string | null;
  external_subscription_id?: string | null;
  provider?: string | null;
  display_name?: string | null;
}

export async function upsertSubscription(userSub: string, data: Subscription) {
  if (!sql) {
    console.warn('[db] No DATABASE_URL provided. Cannot upsert subscription.');
    return null;
  }

  const { plan, status, current_period_end, external_subscription_id, provider, display_name } = data;

  // UPSERT: Insert or update based on user_sub
  const result = await sql`
    INSERT INTO subscriptions (
      user_sub, 
      plan, 
      status, 
      current_period_end, 
      external_subscription_id, 
      provider, 
      display_name,
      updated_at
    ) VALUES (
      ${userSub}, 
      ${plan}, 
      ${status}, 
      ${current_period_end ? new Date(current_period_end) : null}, 
      ${external_subscription_id || null}, 
      ${provider || null}, 
      ${display_name || null},
      NOW()
    )
    ON CONFLICT (user_sub) DO UPDATE SET
      plan = EXCLUDED.plan,
      status = EXCLUDED.status,
      current_period_end = EXCLUDED.current_period_end,
      external_subscription_id = COALESCE(EXCLUDED.external_subscription_id, subscriptions.external_subscription_id),
      provider = COALESCE(EXCLUDED.provider, subscriptions.provider),
      display_name = COALESCE(EXCLUDED.display_name, subscriptions.display_name),
      updated_at = NOW()
    RETURNING *;
  `;

  return result[0] as unknown as Subscription;
}

export async function getSubscription(userSub: string): Promise<Subscription | null> {
  if (!sql) return null;

  const result = await sql`
    SELECT * FROM subscriptions WHERE user_sub = ${userSub} LIMIT 1
  `;
  
  if (result.length === 0) return null;
  
  // Format for the frontend AuthUser type compatibility
  const sub = result[0] as unknown as Subscription;
  return {
    ...sub,
    current_period_end: sub.current_period_end ? (sub.current_period_end as unknown as Date).toISOString() : null,
  };
}

export async function updateSubscription(userSub: string, data: Partial<Subscription>): Promise<Subscription | null> {
  if (!sql) return null;

  // Build dynamic update query
  const updates: Record<string, any> = {};
  if (data.plan) updates.plan = data.plan;
  if (data.status) updates.status = data.status;
  if (data.current_period_end !== undefined) {
    updates.current_period_end = data.current_period_end ? new Date(data.current_period_end) : null;
  }
  if (data.display_name !== undefined) {
    updates.display_name = data.display_name;
  }
  updates.updated_at = sql`NOW()`;

  if (Object.keys(updates).length === 1 && updates.updated_at) {
    return null; // nothing to update
  }

  const result = await sql`
    UPDATE subscriptions
    SET ${sql(updates)}
    WHERE user_sub = ${userSub}
    RETURNING *;
  `;

  return (result[0] as unknown as Subscription) || null;
}

/**
 * Sync the user's role to the backend profiles table so the FastAPI rate-limiter
 * (which reads profiles.role) enforces the correct plan immediately after payment.
 * The backend DB uses profiles.id = user_sub (Logto sub claim).
 */
export async function syncProfileRole(userSub: string, role: string, periodEnd: Date | null): Promise<void> {
  if (!backendSql) {
    // No backend DB configured — this is a real failure for a paid sync, so
    // throw. The webhook's outer handler turns this into a non-2xx response so
    // the payment provider retries instead of silently leaving the user on free.
    throw new Error('VECTOR_DB_URL not configured — cannot sync profile role');
  }
  // NOTE: deliberately NOT caught here. A swallowed error meant a paying user
  // could be left token-capped while the webhook returned 200 and the provider
  // never retried. Let it propagate so the caller can fail the webhook.
  await backendSql`
    INSERT INTO profiles (id, role, subscription_status, subscription_plan, subscription_expires_at, created_at, updated_at)
    VALUES (${userSub}, ${role}, ${role === 'free' ? 'inactive' : 'active'}, ${role}, ${periodEnd}, NOW(), NOW())
    ON CONFLICT (id) DO UPDATE SET
      role = EXCLUDED.role,
      subscription_status = EXCLUDED.subscription_status,
      subscription_plan = EXCLUDED.subscription_plan,
      subscription_expires_at = EXCLUDED.subscription_expires_at,
      updated_at = NOW()
  `;
}

export async function recordPayment(data: {
  user_sub: string;
  razorpay_event_id: string;
  event_type: string;
  payload: any;
}): Promise<boolean> {
  if (!sql) return false;

  try {
    // We rely on the UNIQUE constraint on razorpay_event_id to prevent duplicates
    await sql`
      INSERT INTO payments (
        user_sub,
        razorpay_event_id,
        event_type,
        payload
      ) VALUES (
        ${data.user_sub},
        ${data.razorpay_event_id},
        ${data.event_type},
        ${sql.json(data.payload)}
      )
    `;
    return true; // Successfully inserted new event
  } catch (err: any) {
    // Postgres unique violation error code is '23505'
    if (err.code === '23505') {
      console.log(`[db] Payment event ${data.razorpay_event_id} already processed (idempotent skip).`);
      return false; // Duplicate, safe to ignore
    }
    console.error('[db] Failed to record payment:', err);
    throw err;
  }
}

export interface ConsentInput {
  user_sub?: string | null;
  device_id?: string | null;
  policy_version: string;
  consent_type: string;
  granted?: boolean;
  ip?: string | null;
  user_agent?: string | null;
}

/**
 * Append a consent record (DPDP Act 2023 — consent must be explicit AND
 * demonstrable). Append-only ledger: a withdrawal inserts a new row with
 * granted=false, never a delete, so the audit trail is intact.
 */
export async function recordConsent(data: ConsentInput): Promise<boolean> {
  if (!sql) {
    console.warn('[db] No DATABASE_URL provided. Cannot record consent.');
    return false;
  }
  try {
    await sql`
      INSERT INTO consent_records (
        user_sub, device_id, policy_version, consent_type, granted, ip, user_agent
      ) VALUES (
        ${data.user_sub ?? null},
        ${data.device_id ?? null},
        ${data.policy_version},
        ${data.consent_type},
        ${data.granted ?? true},
        ${data.ip ?? null},
        ${data.user_agent ?? null}
      )
    `;
    return true;
  } catch (err) {
    console.error('[db] Failed to record consent:', err);
    return false;
  }
}
