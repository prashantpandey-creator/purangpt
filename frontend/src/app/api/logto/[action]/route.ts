import { type NextRequest, NextResponse } from 'next/server';
import { signPayload, verifyAndParse, randomBase64url, sha256Base64url, buildSession, setSessionCookie, clearSessionCookie } from '@/lib/auth/session';

// ---------------------------------------------------------------------------
// /api/logto/[action] — Auth routes (Node.js runtime, App Router compatible)
// ---------------------------------------------------------------------------
// We build the OIDC URLs manually rather than using the SDK's handleSignIn
// which is designed for Pages Router and crashes in App Router edge/node
// because it tries to access res.setHeader / req.cookies in incompatible ways.
//
// Session persistence (post-callback) is handled by a signed HttpOnly cookie
// set in /callback using the Web Crypto API (available in Node.js 18+).
// ---------------------------------------------------------------------------

export const runtime = 'nodejs';

// Secrets from env only — no hardcoded fallbacks (committed literals are leaked).
function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing required env var: ${name}`);
  return v;
}

const ENDPOINT   = process.env.LOGTO_ENDPOINT    || 'https://auth.purangpt.com';
const BASE_URL   = process.env.NEXT_PUBLIC_BASE_URL || 'https://purangpt.com';
const REDIRECT_URI  = `${BASE_URL}/api/logto/callback`;
const LOGTO_COOKIE  = 'logto_session';     // email sign-in via Logto
const GOOGLE_COOKIE = 'purangpt_session';  // direct Google OAuth

// Secrets resolved lazily (at request time, inside handlers) — NOT at module load.
// Module-load throws would crash `next build` page-data collection, since these
// env vars only exist at runtime on the server.
const APP_ID        = () => requireEnv('LOGTO_APP_ID');
const APP_SECRET    = () => requireEnv('LOGTO_APP_SECRET');

// ── Route handler ────────────────────────────────────────────────────────────

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ action: string }> }
): Promise<Response> {
  const { action } = await context.params;

  // ── sign-in / sign-up (REMOVED) ──────────────────────────────────────────
  // These previously redirected to Logto's hosted OIDC sign-in page. That path
  // has been removed — all sign-in now goes through our custom UI (SignInModal)
  // with direct Google OAuth (/api/auth/google) or API-driven email auth
  // (/api/auth/email). The Logto callback below is kept for the OIDC protocol
  // which the email auth flow uses server-to-server.
  if (action === 'sign-in' || action === 'sign-up') {
    return NextResponse.redirect(`${BASE_URL}/?error=sign_in_path_removed`);
  }

  // ── callback ──────────────────────────────────────────────────────────────
  if (action === 'callback') {
    const code  = request.nextUrl.searchParams.get('code');
    const state = request.nextUrl.searchParams.get('state');
    const error = request.nextUrl.searchParams.get('error');

    // Surface auth errors gracefully
    if (error) {
      return NextResponse.redirect(`${BASE_URL}/?error=${encodeURIComponent(error)}`);
    }

    if (!code || !state) {
      return NextResponse.redirect(`${BASE_URL}/?error=missing_params`);
    }

    // Verify state + retrieve PKCE verifier
    const pendingCookie = request.cookies.get('logto_pending')?.value;
    const pending = pendingCookie
      ? await verifyAndParse<{ state: string; codeVerifier: string; returnTo: string }>(pendingCookie)
      : null;

    if (!pending || pending.state !== state) {
      return NextResponse.redirect(`${BASE_URL}/?error=state_mismatch`);
    }

    // Exchange code for tokens
    const tokenRes = await fetch(`${ENDPOINT.replace(/\/$/, '')}/oidc/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        grant_type:    'authorization_code',
        client_id:     APP_ID(),
        client_secret: APP_SECRET(),
        code,
        redirect_uri:  REDIRECT_URI,
        code_verifier: pending.codeVerifier,
      }),
    });

    if (!tokenRes.ok) {
      const err = await tokenRes.text();
      console.error('Logto token exchange failed:', err);
      return NextResponse.redirect(`${BASE_URL}/?error=token_exchange`);
    }

    const tokens = await tokenRes.json();

    // Fetch user info
    let userInfo: Record<string, unknown> = {};
    try {
      const uiRes = await fetch(`${ENDPOINT.replace(/\/$/, '')}/oidc/userinfo`, {
        headers: { Authorization: `Bearer ${tokens.access_token}` },
      });
      if (uiRes.ok) userInfo = await uiRes.json();
    } catch { /* non-fatal */ }

    // Store session in a signed cookie
    const session = await buildSession({
      accessToken: tokens.access_token,
      idToken:     tokens.id_token,
      userInfo,
    });

    // returnTo may be relative (e.g. "/pricing"); NextResponse.redirect needs an
    // absolute URL or it throws. Resolve against BASE_URL and guard open-redirects.
    let redirectTo = `${BASE_URL}/chat`;
    try {
      const u = new URL(pending.returnTo || '/chat', BASE_URL);
      if (u.origin === new URL(BASE_URL).origin) redirectTo = u.toString();
    } catch { /* keep default */ }

    const res = NextResponse.redirect(redirectTo);
    setSessionCookie(res, session);
    // Clear the pending cookie
    res.cookies.delete('logto_pending');
    return res;
  }

  // ── sign-out ──────────────────────────────────────────────────────────────
  if (action === 'sign-out') {
    const res = NextResponse.redirect(`${BASE_URL}/`);
    res.cookies.delete(LOGTO_COOKIE);
    res.cookies.delete('purangpt_session');
    res.cookies.delete('logto_pending');
    return res;
  }

  // ── user ────────────────────────────────────────────────────────────────────
  if (action === 'user') {
    // 1. Check direct Google OAuth session first (purangpt_session cookie)
    const googleCookie = request.cookies.get(GOOGLE_COOKIE)?.value;
    if (googleCookie) {
      const gs = await verifyAndParse<{ sub: string; email: string; name: string; picture: string; provider: string; expiresAt: number }>(googleCookie);
      if (gs && Date.now() < gs.expiresAt) {
        return NextResponse.json({ sub: gs.sub, email: gs.email, name: gs.name, picture: gs.picture, provider: gs.provider });
      }
    }

    // 2. Fall back to Logto session (logto_session cookie)
    const logtoCookie = request.cookies.get(LOGTO_COOKIE)?.value;
    if (!logtoCookie) return NextResponse.json(null, { status: 401 });

    const session = await verifyAndParse<{ user: Record<string, unknown>; expiresAt: number }>(logtoCookie);
    if (!session) return NextResponse.json(null, { status: 401 });
    if (Date.now() > session.expiresAt) {
      const res = NextResponse.json(null, { status: 401 });
      res.cookies.delete(LOGTO_COOKIE);
      return res;
    }
    return NextResponse.json(session.user);
  }

  return NextResponse.json({ error: 'Unknown action' }, { status: 404 });
}
