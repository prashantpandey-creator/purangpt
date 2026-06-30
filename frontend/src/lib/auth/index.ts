/**
 * getAccessToken — Client-side access token resolver.
 *
 * Called by api.ts before every chat request. Fetches the active Bearer token
 * from /api/logto/token (which reads the signed session cookie server-side and
 * returns the Logto or Google access_token). Returns null for guests so the
 * backend applies its guest rate limit.
 *
 * The result is NOT cached — each call fetches fresh, so a token refresh that
 * updates the cookie is picked up by the very next request.
 */
export async function getAccessToken(): Promise<string | null> {
  try {
    const res = await fetch("/api/logto/token", { credentials: "include" });
    if (!res.ok) return null;
    const data = await res.json();
    return data?.token || null;
  } catch {
    return null;
  }
}
