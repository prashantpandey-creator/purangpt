import { type NextRequest, NextResponse } from 'next/server';

// ---------------------------------------------------------------------------
// Direct Google OAuth 2.0 — completely bypasses Logto
// GET /api/auth/google         → redirect to Google's consent screen
// GET /api/auth/google/callback → exchange code, write session, redirect home
// ---------------------------------------------------------------------------

export const runtime = 'nodejs';

// Secrets from env only — no hardcoded fallbacks (committed literals are leaked
// forever and let attackers impersonate the OAuth app or forge sessions).
function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing required env var: ${name}`);
  return v;
}

const GOOGLE_CLIENT_ID     = () => requireEnv('GOOGLE_CLIENT_ID');
const GOOGLE_CLIENT_SECRET = () => requireEnv('GOOGLE_CLIENT_SECRET');
const SESSION_COOKIE       = 'purangpt_session';
const COOKIE_SECRET        = () => requireEnv('LOGTO_COOKIE_SECRET');

// ── Crypto helpers ───────────────────────────────────────────────────────────

function randomBase64url(bytes = 32): string {
  const arr = new Uint8Array(bytes);
  crypto.getRandomValues(arr);
  return Buffer.from(arr).toString('base64url');
}

async function signPayload(payload: object): Promise<string> {
  const key = await crypto.subtle.importKey(
    'raw', new TextEncoder().encode(COOKIE_SECRET()),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']
  );
  const data = JSON.stringify(payload);
  const sig  = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(data));
  return `${Buffer.from(data).toString('base64url')}.${Buffer.from(sig).toString('base64url')}`;
}

async function verifyAndParse<T>(cookie: string): Promise<T | null> {
  try {
    const [dataB64, sigB64] = cookie.split('.');
    const data = Buffer.from(dataB64, 'base64url').toString();
    const key  = await crypto.subtle.importKey(
      'raw', new TextEncoder().encode(COOKIE_SECRET()),
      { name: 'HMAC', hash: 'SHA-256' }, false, ['verify']
    );
    const valid = await crypto.subtle.verify(
      'HMAC', key,
      Buffer.from(sigB64, 'base64url'),
      new TextEncoder().encode(data)
    );
    return valid ? JSON.parse(data) : null;
  } catch { return null; }
}

// ── Route handler ────────────────────────────────────────────────────────────

// In Docker/production, request.nextUrl.origin resolves to the bind address
// (e.g. 0.0.0.0:3000), which makes the OAuth redirect_uri invalid and Google
// rejects the sign-in. Prefer an explicit public domain. We accept either
// NEXTAUTH_URL or NEXT_PUBLIC_BASE_URL (the var the Logto flow already uses) so
// setting just one env var keeps BOTH auth flows working. Only fall back to the
// request origin in local dev where neither is set.
function getPublicOrigin(request: NextRequest): string {
  const explicit = process.env.NEXTAUTH_URL || process.env.NEXT_PUBLIC_BASE_URL;
  if (explicit) return explicit.replace(/\/$/, '');
  return request.nextUrl.origin;
}

export async function GET(request: NextRequest): Promise<Response> {
  const origin   = getPublicOrigin(request);
  const returnTo = request.nextUrl.searchParams.get('returnTo') || `${origin}/chat`;
  const state    = randomBase64url();

  // Stash state + returnTo in short-lived cookie
  const pending = await signPayload({ state, returnTo });

  const callbackUrl = `${origin}/api/auth/google/callback`;

  const googleUrl = new URL('https://accounts.google.com/o/oauth2/v2/auth');
  googleUrl.searchParams.set('client_id',     GOOGLE_CLIENT_ID());
  googleUrl.searchParams.set('redirect_uri',  callbackUrl);
  googleUrl.searchParams.set('response_type', 'code');
  googleUrl.searchParams.set('scope',         'openid email profile');
  googleUrl.searchParams.set('state',         state);
  googleUrl.searchParams.set('prompt',        'consent');
  googleUrl.searchParams.set('access_type',   'offline');    // request refresh_token for long-lived sessions

  const res = NextResponse.redirect(googleUrl.toString());
  res.cookies.set('google_pending', pending, {
    httpOnly: true,
    secure:   process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge:   600,
    path:     '/',
  });
  return res;
}
