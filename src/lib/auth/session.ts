/**
 * Shared session utilities — HMAC-signed cookie helpers used by all auth routes.
 * Extracted from api/logto/[action]/route.ts so the email-auth route can reuse them.
 */

const LOGTO_COOKIE = 'logto_session';

function requireEnv(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`Missing required env var: ${name}`);
  return v;
}

function cookieSecret(): string {
  return requireEnv('LOGTO_COOKIE_SECRET');
}

// ── Crypto ────────────────────────────────────────────────────────────────────

function randomBase64url(bytes = 32): string {
  const arr = new Uint8Array(bytes);
  crypto.getRandomValues(arr);
  return Buffer.from(arr).toString('base64url');
}

async function sha256Base64url(plain: string): Promise<string> {
  const enc = new TextEncoder();
  const digest = await crypto.subtle.digest('SHA-256', enc.encode(plain));
  return Buffer.from(digest).toString('base64url');
}

// ── Session signing / verification ────────────────────────────────────────────

export async function signPayload(payload: object): Promise<string> {
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(cookieSecret()),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign'],
  );
  const data = JSON.stringify(payload);
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(data));
  const sigB64 = Buffer.from(sig).toString('base64url');
  return `${Buffer.from(data).toString('base64url')}.${sigB64}`;
}

export async function verifyAndParse<T>(cookie: string): Promise<T | null> {
  try {
    const [dataB64, sigB64] = cookie.split('.');
    const data = Buffer.from(dataB64, 'base64url').toString();
    const key = await crypto.subtle.importKey(
      'raw',
      new TextEncoder().encode(cookieSecret()),
      { name: 'HMAC', hash: 'SHA-256' },
      false,
      ['verify'],
    );
    const valid = await crypto.subtle.verify(
      'HMAC',
      key,
      Buffer.from(sigB64, 'base64url'),
      new TextEncoder().encode(data),
    );
    return valid ? JSON.parse(data) : null;
  } catch {
    return null;
  }
}

// ── PKCE helpers (for email auth flow) ─────────────────────────────────────────

export { randomBase64url, sha256Base64url };

// ── Cookie helpers ─────────────────────────────────────────────────────────────

interface CookieBag {
  set(name: string, value: string, opts: Record<string, unknown>): void;
  delete(name: string): void;
}

type NextLikeResponse = Response & { cookies: CookieBag };

export function setSessionCookie(
  res: Response,
  session: string,
  maxAge = 60 * 60 * 24 * 7, // 7 days
): void {
  const nextRes = res as NextLikeResponse;
  nextRes.cookies.set(LOGTO_COOKIE, session, {
    httpOnly: true,
    secure: true,
    sameSite: 'none',         // WKWebView requires SameSite=None for persistent cookies
    maxAge,
    path: '/',
  });
}

export function clearSessionCookie(res: Response): void {
  const nextRes = res as NextLikeResponse;
  nextRes.cookies.delete(LOGTO_COOKIE);
}

/**
 * Build a signed session cookie value from Logto tokens + userinfo.
 */
export async function buildSession(options: {
  accessToken: string;
  idToken?: string;
  userInfo: Record<string, unknown>;
  expiresAt?: number;
}): Promise<string> {
  return signPayload({
    user: options.userInfo,
    accessToken: options.accessToken,
    idToken: options.idToken ?? null,
    expiresAt: options.expiresAt ?? Date.now() + 7 * 24 * 60 * 60 * 1000,
  });
}
