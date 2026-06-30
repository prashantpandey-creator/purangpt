import { type NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';

const LOGTO_COOKIE   = 'logto_session';
const GOOGLE_COOKIE  = 'purangpt_session';
// No hardcoded fallback — resolved lazily (request time, not module load) so the
// missing-env throw can't crash `next build` page-data collection.
const COOKIE_SECRET = () => {
  const v = process.env.LOGTO_COOKIE_SECRET;
  if (!v) throw new Error('Missing required env var: LOGTO_COOKIE_SECRET');
  return v;
};

async function verifyAndParse<T>(cookie: string): Promise<T | null> {
  try {
    const [dataB64, sigB64] = cookie.split('.');
    const data = Buffer.from(dataB64, 'base64url').toString();
    const key = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(COOKIE_SECRET()),
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['verify']
    );
    const valid = await crypto.subtle.verify(
      'HMAC', key,
      Buffer.from(sigB64, 'base64url'),
      new TextEncoder().encode(data)
    );
    return valid ? JSON.parse(data) : null;
  } catch {
    return null;
  }
}

/**
 * GET /api/logto/token
 * Returns a bearer token for the FastAPI backend.
 * Prefers the Logto access token; falls back to the Google access token for
 * users who authenticated via the direct Google OAuth flow. Both token types
 * are verified by the FastAPI auth.py backend.
 */
export async function GET(request: NextRequest) {
  // 1. Try Logto session first (the primary auth path for email/social via Logto)
  const logtoCookie = request.cookies.get(LOGTO_COOKIE)?.value;
  if (logtoCookie) {
    const session = await verifyAndParse<{
      accessToken: string;
      expiresAt: number;
    }>(logtoCookie);
    if (session && Date.now() <= session.expiresAt && session.accessToken) {
      return NextResponse.json({ token: session.accessToken, provider: 'logto' });
    }
  }

  // 2. Fall back to Google OAuth session. The Google access_token is a short-lived
  // opaque token (not a JWT) that the FastAPI backend verifies via Google tokeninfo.
  const googleCookie = request.cookies.get(GOOGLE_COOKIE)?.value;
  if (googleCookie) {
    const session = await verifyAndParse<{
      accessToken: string;
      expiresAt: number;
      sub: string;
      email: string;
      provider: string;
    }>(googleCookie);
    if (session && Date.now() <= session.expiresAt && session.accessToken) {
      return NextResponse.json({ token: session.accessToken, provider: 'google' });
    }
  }

  return NextResponse.json({ token: null }, { status: 401 });
}
