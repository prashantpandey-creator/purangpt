/**
 * POST /api/auth/refresh — Refresh an expired Google OAuth access_token.
 *
 * Called periodically by the AuthContext health check when the session appears
 * expired. Uses the refresh_token stored in the purangpt_session cookie to
 * obtain a new access_token from Google. On success, the session cookie is
 * updated in-place so the user never sees a "signed out" state.
 */

import { type NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';

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

export async function POST(request: NextRequest): Promise<Response> {
  const googleCookie = request.cookies.get(SESSION_COOKIE)?.value;
  if (!googleCookie) {
    return NextResponse.json({ error: 'No session' }, { status: 401 });
  }

  const session = await verifyAndParse<{
    sub: string; email: string; name: string; picture: string;
    provider: string; accessToken: string; refreshToken: string | null;
    expiresAt: number;
  }>(googleCookie);

  if (!session || Date.now() > session.expiresAt) {
    return NextResponse.json({ error: 'Session expired' }, { status: 401 });
  }

  if (!session.refreshToken) {
    return NextResponse.json({ error: 'No refresh token — re-authentication required' }, { status: 401 });
  }

  // Exchange refresh_token for a new access_token
  const tokenRes = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      client_id:     GOOGLE_CLIENT_ID(),
      client_secret: GOOGLE_CLIENT_SECRET(),
      grant_type:    'refresh_token',
      refresh_token: session.refreshToken,
    }),
  });

  if (!tokenRes.ok) {
    console.error('[auth/refresh] Google token refresh failed:', await tokenRes.text());
    return NextResponse.json({ error: 'Refresh failed — re-authentication required' }, { status: 401 });
  }

  const tokens = await tokenRes.json();

  // Update the session cookie with the new access_token (and possibly new refresh_token)
  const newSession = await signPayload({
    sub:          session.sub,
    email:        session.email,
    name:         session.name,
    picture:      session.picture,
    provider:     'google',
    accessToken:  tokens.access_token,
    refreshToken: tokens.refresh_token || session.refreshToken,
    expiresAt:    Date.now() + 7 * 24 * 60 * 60 * 1000,
  });

  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, newSession, {
    httpOnly: true,
    secure:   process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge:   60 * 60 * 24 * 7, // 7 days
    path:     '/',
  });
  return res;
}
