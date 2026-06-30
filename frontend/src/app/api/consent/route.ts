import { type NextRequest, NextResponse } from "next/server";
import { getSessionUser } from "@/lib/session";
import { recordConsent, type ConsentInput } from "@/lib/db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

/**
 * POST /api/consent — record explicit user consent (DPDP Act 2023).
 *
 * Called the instant the user ticks "I agree", BEFORE the OAuth redirect — so
 * they are typically not authenticated yet. We key the row by device_id now
 * (user_sub is backfilled once OAuth resolves and the profile is known) and
 * stamp the server-trusted ip + user_agent + timestamp the client can't forge.
 */
export async function POST(request: NextRequest): Promise<Response> {
  let body: { policyVersion?: string; consentType?: string; deviceId?: string | null };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const policy_version = body.policyVersion?.trim();
  if (!policy_version) {
    return NextResponse.json({ error: "policyVersion is required" }, { status: 400 });
  }

  // If the user is already signed in (e.g. re-consent on a policy change), tie the
  // record to their sub; otherwise it's an anonymous pre-auth consent keyed by device.
  const user = await getSessionUser(request);

  const xff = request.headers.get("x-forwarded-for");
  const ip = xff ? xff.split(",")[0].trim() : request.headers.get("x-real-ip");

  const record: ConsentInput = {
    user_sub: user?.sub ?? null,
    device_id: body.deviceId ?? null,
    policy_version,
    consent_type: body.consentType?.trim() || "signup",
    granted: true,
    ip,
    user_agent: request.headers.get("user-agent"),
  };

  const ok = await recordConsent(record);
  if (!ok) {
    return NextResponse.json({ error: "Failed to record consent" }, { status: 500 });
  }
  return NextResponse.json({ recorded: true }, { status: 201 });
}
