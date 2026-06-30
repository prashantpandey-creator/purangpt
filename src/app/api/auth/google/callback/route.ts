import { type NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';

// Secrets from env only — no hardcoded fallbacks (see google/route.ts).
function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing required env var: ${name}`);
  return v;
}

const GOOGLE_CLIENT_ID     = () => requireEnv('GOOGLE_CLIENT_ID');
const GOOGLE_CLIENT_SECRET = () => requireEnv('GOOGLE_CLIENT_SECRET');
const SESSION_COOKIE       = 'purangpt_session';
const COOKIE_SECRET        = () => requireEnv('LOGTO_COOKIE_SECRET');

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

// In Docker, request.nextUrl.origin resolves to the bind address (0.0.0.0:3000).
// Prefer an explicit public domain (NEXTAUTH_URL or NEXT_PUBLIC_BASE_URL) so the
// token-exchange redirect_uri matches the one used in the auth request. MUST stay
// in sync with google/route.ts — a mismatch fails the token exchange.
function getPublicOrigin(request: NextRequest): string {
  const explicit = process.env.NEXTAUTH_URL || process.env.NEXT_PUBLIC_BASE_URL;
  if (explicit) return explicit.replace(/\/$/, '');
  return request.nextUrl.origin;
}

// returnTo may be a relative path (e.g. "/pricing") when sign-in starts from an
// in-app page. NextResponse.redirect() requires an ABSOLUTE URL or it throws, so
// resolve relative paths against our origin. Reject off-site absolute URLs.
function safeReturnTo(returnTo: string | undefined, origin: string): string {
  if (!returnTo) return `${origin}/chat`;
  try {
    const u = new URL(returnTo, origin);
    // Only allow redirects back to our own origin (open-redirect guard).
    if (u.origin !== new URL(origin).origin) return `${origin}/chat`;
    return u.toString();
  } catch {
    return `${origin}/chat`;
  }
}

export async function GET(request: NextRequest): Promise<Response> {
  const code  = request.nextUrl.searchParams.get('code');
  const state = request.nextUrl.searchParams.get('state');
  const error = request.nextUrl.searchParams.get('error');

  const origin = getPublicOrigin(request);

  if (error) {
    return NextResponse.redirect(`${origin}/?auth_error=${encodeURIComponent(error)}`);
  }

  if (!code || !state) {
    return NextResponse.redirect(`${origin}/?auth_error=missing_params`);
  }

  // Verify state cookie — cookie holds the signed payload, not the raw state
  const pendingCookie = request.cookies.get('google_pending');
  if (!pendingCookie) {
    return NextResponse.redirect(`${origin}/?auth_error=no_pending_cookie`);
  }

  const pendingData = await verifyAndParse<{ state: string, returnTo: string }>(pendingCookie.value);
  if (!pendingData || pendingData.state !== state) {
    return NextResponse.redirect(`${origin}/?auth_error=invalid_state`);
  }

  const callbackUrl = `${origin}/api/auth/google/callback`;

  // 1. Exchange code for tokens
  const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      code,
      client_id:     GOOGLE_CLIENT_ID(),
      client_secret: GOOGLE_CLIENT_SECRET(),
      grant_type:    'authorization_code',
      redirect_uri:  callbackUrl,
    }),
  });

  if (!tokenRes.ok) {
    const err = await tokenRes.text();
    console.error('Token exchange failed:', err);
    return NextResponse.redirect(`${origin}/?auth_error=token_failed`);
  }

  const tokens = await tokenRes.json();

  // Fetch Google user profile
  const profileRes = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
  });

  if (!profileRes.ok) {
    return NextResponse.redirect(`${origin}/?auth_error=profile_failed`);
  }

  const profile = await profileRes.json();
  // Google userinfo shape: { sub, email, name, picture, email_verified, ... }

  // Write session cookie (7 days). The Google access_token expires in ~1h, but we
  // also store the refresh_token so /api/auth/refresh can silently renew the
  // access_token without the user re-authenticating. refresh_token may be absent if
  // the user previously granted offline access (Google only re-issues on prompt=consent).
  const session = await signPayload({
    sub:          profile.sub,
    email:        profile.email,
    name:         profile.name,
    picture:      profile.picture,
    provider:     'google',
    accessToken:  tokens.access_token,
    refreshToken: tokens.refresh_token || null,
    expiresAt:    Date.now() + 7 * 24 * 60 * 60 * 1000,
  });

  const res = NextResponse.redirect(safeReturnTo(pendingData.returnTo, origin));
  res.cookies.set(SESSION_COOKIE, session, {
    httpOnly: true,
    secure:   true,
    sameSite: 'none',         // WKWebView requires SameSite=None for persistent cookies
    maxAge:   60 * 60 * 24 * 7, // 7 days
    path:     '/',
  });
  res.cookies.delete('google_pending');
  return res;
}
