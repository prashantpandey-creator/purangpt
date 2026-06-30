/**
 * session.ts — Server-side session parsing.
 * Reads the purangpt_session (Google) or logto_session (Logto email) cookie
 * and returns a unified user shape.
 */

// No hardcoded fallback — this signs/verifies every session cookie, so a literal
// here would let anyone forge a valid session for any user. Resolved lazily (at
// request time, not module load) so `next build` doesn't fail when the var is
// only present at runtime; it still throws before any cookie is signed/verified.
function getCookieSecret(): string {
  const v = process.env.LOGTO_COOKIE_SECRET;
  if (!v) throw new Error('Missing required env var: LOGTO_COOKIE_SECRET');
  return v;
}

export interface SessionUser {
  sub: string;
  email: string;
  name: string;
  picture: string;
  provider: 'google' | 'logto';
}

async function verifyHmac<T>(cookie: string): Promise<T | null> {
  try {
    const [dataB64, sigB64] = cookie.split('.');
    if (!dataB64 || !sigB64) return null;
    const data = Buffer.from(dataB64, 'base64url').toString();
    const key = await crypto.subtle.importKey(
      'raw', new TextEncoder().encode(getCookieSecret()),
      { name: 'HMAC', hash: 'SHA-256' }, false, ['verify']
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
 * Resolve the current user from a request's cookies (Google or Logto session).
 * Returns null when no valid session is present.
 */
export async function getSessionUser(request: {
  cookies: { get(name: string): { value: string } | undefined };
}): Promise<SessionUser | null> {
  const googleCookie = request.cookies.get('purangpt_session')?.value;
  const logtoCookie = request.cookies.get('logto_session')?.value;
  return (
    (googleCookie ? await parseGoogleSession(googleCookie) : null) ??
    (logtoCookie ? await parseLogtoSession(logtoCookie) : null)
  );
}

/** Parse a Google purangpt_session cookie into a SessionUser. */
export async function parseGoogleSession(raw: string): Promise<SessionUser | null> {
  const s = await verifyHmac<{
    sub: string; email: string; name: string; picture: string;
    provider: string; expiresAt: number;
  }>(raw);
  if (!s || Date.now() > s.expiresAt) return null;
  return { sub: s.sub, email: s.email, name: s.name, picture: s.picture, provider: 'google' };
}

/** Parse a Logto logto_session cookie into a SessionUser. */
export async function parseLogtoSession(raw: string): Promise<SessionUser | null> {
  const s = await verifyHmac<{
    user: { sub?: string; email?: string; name?: string; picture?: string };
    expiresAt: number;
  }>(raw);
  if (!s || Date.now() > s.expiresAt) return null;
  const u = s.user;
  if (!u?.sub) return null;
  return {
    sub: u.sub,
    email: u.email ?? '',
    name: u.name ?? '',
    picture: u.picture ?? '',
    provider: 'logto',
  };
}
