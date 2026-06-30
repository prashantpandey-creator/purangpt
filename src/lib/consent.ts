/**
 * Consent policy versioning + client-side recorder.
 *
 * India's DPDP Act 2023 requires consent that is explicit, informed, and
 * *demonstrable*. The checkbox provides the explicit affirmative action; this
 * module records WHICH policy version the user agreed to so we can prove it.
 *
 * Bump POLICY_VERSION whenever Terms or Privacy change materially — DPDP expects
 * re-consent on material change, and each row pins the exact text consented to.
 */
export const POLICY_VERSION = "terms@2026-06-27,privacy@2026-06-27";

export type ConsentType = "signup" | "recurring_payment" | "marketing";

/**
 * Record explicit consent at the moment of the affirmative tick — fired from the
 * client just before the OAuth redirect. Best-effort: a network failure must NOT
 * block sign-in (the legal gate is the checkbox; this is the audit trail).
 * `keepalive` lets the POST survive the imminent navigation to the OAuth provider.
 */
export async function recordConsent(opts: {
  consentType?: ConsentType;
  deviceId?: string | null;
}): Promise<void> {
  try {
    await fetch("/api/consent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        policyVersion: POLICY_VERSION,
        consentType: opts.consentType ?? "signup",
        deviceId: opts.deviceId ?? null,
      }),
      keepalive: true,
    });
  } catch {
    /* best-effort — never block sign-in on a logging failure */
  }
}
