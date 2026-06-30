import { type NextRequest, NextResponse } from "next/server";
import { getSessionUser } from "@/lib/session";

export const runtime = "nodejs";

/**
 * Catch-all proxy: /api/growth/<...> → growth_engine FastAPI (default :8100).
 *
 * The growth_engine app is internal — it is never exposed to the browser. This
 * route is the single trusted door:
 *   1. Gate on the signed session cookie (getSessionUser) → 401 if absent.
 *   2. Forward to the FastAPI with `X-User-Sub: <session.sub>`, which app.py's
 *      get_user() dependency reads. The internal service key (if set) marks the
 *      call as trusted so the backend honours the forwarded identity.
 *
 * So the browser holds no growth-engine URL and no service key; credentials and
 * vault writes happen server-side only — same trust model as /api/v1/chat.
 */
const GROWTH_URL =
  process.env.GROWTH_ENGINE_URL || "http://127.0.0.1:8100";
const INTERNAL_KEY = process.env.INTERNAL_SERVICE_KEY || "";

/**
 * Per-session sliding-window limiter (in-memory, per-worker).
 *
 * This route is session-gated, so we key on user.sub rather than IP. The
 * /campaigns/:id/generate path spawns N LLM calls per channel — left unthrottled,
 * a single session could fan out unbounded generation. The Traefik edge limiter
 * covers the per-IP burst case for this host too; this is the per-IDENTITY wall.
 *
 * In-memory is acceptable here: it resets on deploy and is per-worker (so the
 * real ceiling is limit × workers), but combined with the edge limit and the
 * backend's own per-day quota it's sufficient defense-in-depth. A Redis-backed
 * version would be the upgrade if growth traffic ever justifies it.
 */
const _hits = new Map<string, number[]>();
function rateLimited(key: string, limit: number, windowMs: number): boolean {
  const now = Date.now();
  const arr = (_hits.get(key) || []).filter((t) => t > now - windowMs);
  arr.push(now);
  _hits.set(key, arr);
  // Opportunistic cleanup so the Map doesn't grow unbounded.
  if (_hits.size > 5000) {
    for (const [k, v] of _hits) {
      if (v.every((t) => t <= now - windowMs)) _hits.delete(k);
    }
  }
  return arr.length > limit;
}

async function proxy(
  request: NextRequest,
  path: string[],
): Promise<Response> {
  const user = await getSessionUser(request);
  if (!user) {
    return NextResponse.json(
      { error: "Sign in to manage growth campaigns." },
      { status: 401 },
    );
  }

  const subpath = path.join("/");

  // Per-session throttle. The generate path spawns LLM calls, so it gets a far
  // tighter budget than cheap reads (connections/campaigns/queue listings).
  const isGenerate = subpath.includes("/generate");
  const limited = isGenerate
    ? rateLimited(`gen:${user.sub}`, 5, 60_000) // 5 generations / minute
    : rateLimited(`api:${user.sub}`, 60, 60_000); // 60 reads / minute
  if (limited) {
    return NextResponse.json(
      { error: "Too many requests. Please slow down and retry shortly." },
      { status: 429, headers: { "Retry-After": "10" } },
    );
  }

  const qs = request.nextUrl.search; // preserve ?days=7 etc.
  const target = `${GROWTH_URL}/${subpath}${qs}`;

  const headers: Record<string, string> = {
    "X-User-Sub": user.sub,
  };
  if (INTERNAL_KEY) headers["X-Internal-Service-Key"] = INTERNAL_KEY;

  // Forward the body for mutating methods only.
  let body: string | undefined;
  if (request.method !== "GET" && request.method !== "DELETE") {
    body = await request.text();
    if (body) headers["Content-Type"] = "application/json";
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
    });
  } catch {
    return NextResponse.json(
      { error: "Growth engine unavailable. Is the worker running?" },
      { status: 502 },
    );
  }

  // SSE passthrough for the campaign-generate stream.
  const ct = upstream.headers.get("content-type") || "";
  if (ct.includes("text/event-stream") && upstream.body) {
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        Connection: "keep-alive",
      },
    });
  }

  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: { "Content-Type": ct || "application/json" },
  });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(request, path);
}
export async function POST(request: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(request, path);
}
export async function DELETE(request: NextRequest, ctx: Ctx) {
  const { path } = await ctx.params;
  return proxy(request, path);
}
