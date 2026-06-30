/**
 * Capacitor (mobile) Logto config — public endpoint + appId only, NO secrets.
 * Imported by AuthContext for the Capacitor native auth path (iOS/Android).
 *
 * Server-side Logto SDK (getLogtoConfig / getLogtoClient) was removed 2026-06-30:
 * the web auth flow now handles OIDC manually (manual token exchange, manual
 * HMAC cookie signing). The SDK was only used for the removed Logto hosted UI.
 */

// The capacitor (mobile) config — public values only. Do NOT add secrets here;
// it is imported by client-side AuthContext.
export const logtoCapacitorConfig = {
  endpoint: process.env.NEXT_PUBLIC_LOGTO_ENDPOINT || 'https://auth.purangpt.com/',
  appId: process.env.NEXT_PUBLIC_LOGTO_APP_ID || 't43ntgaztl5izt1h78lwc',
};
