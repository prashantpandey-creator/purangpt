/**
 * POST /api/auth/email — Custom email/password sign-in (bypasses Logto hosted UI).
 *
 * The client sends email + password; this route calls Logto's internal sign-in API
 * server-to-server, extracts the auth code, exchanges it for tokens, fetches the
 * user profile, and sets the signed logto_session cookie directly — no redirect,
 * no Logto-branded page.
 */

import { NextRequest, NextResponse } from 'next/server';
import { buildSession, setSessionCookie } from '@/lib/auth/session';

export const runtime = 'nodejs';

function env(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing env: ${name}`);
  return v;
}

const LOGTO_ENDPOINT = (process.env.LOGTO_ENDPOINT || 'https://auth.purangpt.com').replace(/\/$/, '');
const BASE_URL = process.env.NEXT_PUBLIC_BASE_URL || 'https://purangpt.com';

/**
 * Follow a redirect chain server-side, extracting cookies along the way, until we
 * land on our own callback URL. Returns the auth code from the final URL.
 */
async function extractAuthCode(
  startUrl: string,
  initialCookies: string[],
): Promise<{ code: string; cookies: string[] }> {
  let url = startUrl;
  const jar: string[] = [...initialCookies];

  // Safety: max 5 redirects
  for (let i = 0; i < 5; i++) {
    // Resolve relative URLs against Logto's origin
    const fullUrl = url.startsWith('http') ? url : `${LOGTO_ENDPOINT}${url}`;

    const res = await fetch(fullUrl, {
      redirect: 'manual',
      headers: jar.length ? { cookie: jar.join('; ') } : {},
    });

    // Collect any new cookies
    const setCookie = res.headers.getSetCookie?.() ?? res.headers.get('set-cookie');
    if (setCookie) {
      // Extract cookie name=value pairs (ignore HttpOnly/Secure/Path/Domain attrs)
      const pairs = (Array.isArray(setCookie) ? setCookie : [setCookie])
        .map((c) => c.split(';')[0].trim())
        .filter(Boolean);
      for (const pair of pairs) {
        // Replace existing cookie with same name, or append
        const name = pair.split('=')[0];
        const idx = jar.findIndex((c) => c.startsWith(`${name}=`));
        if (idx >= 0) jar[idx] = pair;
        else jar.push(pair);
      }
    }

    const location = res.headers.get('location');

    // If we landed on our own callback URL, extract the code
    if (location && location.startsWith(BASE_URL)) {
      const locUrl = new URL(location);
      const code = locUrl.searchParams.get('code');
      if (code) return { code, cookies: jar };
      throw new Error('No code in callback URL');
    }

    // Follow redirect
    if (location) {
      url = location;
      continue;
    }

    // No redirect — check if the response body itself is a JSON with redirectTo
    if (res.ok) {
      try {
        const body = await res.json();
        if (body.redirectTo) {
          url = body.redirectTo;
          continue;
        }
      } catch {
        // Not JSON — dead end
      }
    }

    throw new Error(`Unexpected response at ${fullUrl}: ${res.status}`);
  }

  throw new Error('Too many redirects');
}

export async function POST(request: NextRequest): Promise<Response> {
  let body: { email?: string; password?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const { email, password } = body;
  if (!email || !password) {
    return NextResponse.json({ error: 'Email and password are required' }, { status: 400 });
  }

  // ── 1. Call Logto's sign-in API ──────────────────────────────────────────
  let signInRes: Response;
  try {
    signInRes = await fetch(`${LOGTO_ENDPOINT}/api/sign-in`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ identifier: { email }, password }),
      redirect: 'manual',
    });
  } catch (e) {
    console.error('[email-auth] Logto sign-in unreachable:', e);
    return NextResponse.json({ error: 'Authentication service unavailable' }, { status: 502 });
  }

  // Collect cookies from Logto's response
  const setCookie = signInRes.headers.getSetCookie?.() ?? signInRes.headers.get('set-cookie');
  const initialCookies: string[] = [];
  if (setCookie) {
    const pairs = (Array.isArray(setCookie) ? setCookie : [setCookie])
      .map((c) => c.split(';')[0].trim())
      .filter(Boolean);
    initialCookies.push(...pairs);
  }

  // ── 2. Parse sign-in response ────────────────────────────────────────────
  let signInData: Record<string, unknown>;

  // Logto may return 200 with JSON, or a redirect
  if (signInRes.ok) {
    try {
      signInData = await signInRes.json();
    } catch {
      return NextResponse.json({ error: 'Unexpected response from auth service' }, { status: 502 });
    }
  } else {
    // Error response — try to extract a human-readable message
    try {
      signInData = await signInRes.json();
    } catch {
      return NextResponse.json({ error: 'Authentication failed' }, { status: 401 });
    }
    const msg =
      (signInData.message as string) ||
      (signInData.error_description as string) ||
      'Invalid email or password';
    return NextResponse.json({ error: msg }, { status: 401 });
  }

  // MFA / verification required
  if (signInData.verificationId) {
    return NextResponse.json({
      verificationRequired: true,
      verificationId: signInData.verificationId,
    });
  }

  // ── 3. Extract auth code ─────────────────────────────────────────────────
  let code: string | null = null;

  // Case A: sign-in returned a redirectTo URL
  const redirectTo = signInData.redirectTo as string | undefined;
  if (redirectTo) {
    try {
      // Check if redirectTo already points to our callback
      if (redirectTo.startsWith(BASE_URL)) {
        const redirUrl = new URL(redirectTo);
        code = redirUrl.searchParams.get('code');
      } else {
        // Follow the redirect chain through Logto's internals
        const result = await extractAuthCode(redirectTo, initialCookies);
        code = result.code;
      }
    } catch (e) {
      console.error('[email-auth] Failed to extract auth code:', e);
    }
  }

  // Case B: sign-in returned a 303/302 redirect directly
  if (!code) {
    const location = signInRes.headers.get('location');
    if (location) {
      try {
        if (location.startsWith(BASE_URL)) {
          const locUrl = new URL(location);
          code = locUrl.searchParams.get('code');
        } else {
          const result = await extractAuthCode(location, initialCookies);
          code = result.code;
        }
      } catch (e) {
        console.error('[email-auth] Failed to follow redirect:', e);
      }
    }
  }

  if (!code) {
    // Last resort: try the response body directly for a code-like token
    const raw =
      signInData.code ||
      signInData.authorization_code ||
      null;
    if (typeof raw === 'string') code = raw;
  }

  if (!code) {
    console.error('[email-auth] No auth code in sign-in response:', JSON.stringify(signInData).slice(0, 500));
    return NextResponse.json({ error: 'Authentication failed — could not complete sign-in' }, { status: 500 });
  }

  // ── 4. Exchange code for tokens ──────────────────────────────────────────
  let tokens: { access_token: string; id_token?: string };
  try {
    const tokenRes = await fetch(`${LOGTO_ENDPOINT}/oidc/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type: 'authorization_code',
        client_id: env('LOGTO_APP_ID'),
        client_secret: env('LOGTO_APP_SECRET'),
        code,
        redirect_uri: `${BASE_URL}/api/logto/callback`,
      }),
    });

    if (!tokenRes.ok) {
      const errText = await tokenRes.text();
      console.error('[email-auth] Token exchange failed:', errText);
      return NextResponse.json({ error: 'Authentication failed at token exchange' }, { status: 500 });
    }

    tokens = await tokenRes.json();
  } catch (e) {
    console.error('[email-auth] Token exchange error:', e);
    return NextResponse.json({ error: 'Token exchange failed' }, { status: 502 });
  }

  // ── 5. Fetch userinfo ────────────────────────────────────────────────────
  let userInfo: Record<string, unknown> = {};
  try {
    const uiRes = await fetch(`${LOGTO_ENDPOINT}/oidc/userinfo`, {
      headers: { Authorization: `Bearer ${tokens.access_token}` },
    });
    if (uiRes.ok) userInfo = await uiRes.json();
  } catch {
    // Non-fatal — session still works without full profile
  }

  // ── 6. Build session, set cookie, return ─────────────────────────────────
  const session = await buildSession({
    accessToken: tokens.access_token,
    idToken: tokens.id_token,
    userInfo,
  });

  const res = NextResponse.json({ success: true, user: userInfo });
  setSessionCookie(res, session);
  return res;
}
