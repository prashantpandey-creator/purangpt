import Foundation

/// Logto OIDC configuration for the native iOS client.
///
/// All values here are PUBLIC — they already ship to the browser via
/// `logtoCapacitorConfig` in `src/lib/logto.ts`. A native OIDC public client
/// uses Authorization Code + PKCE and needs NO app secret.
///
/// Endpoints confirmed against the live discovery doc at
/// https://auth.purangpt.com/oidc/.well-known/openid-configuration.
enum AuthConfig {
    static let issuer = "https://auth.purangpt.com/oidc"
    static let authorizationEndpoint = URL(string: "https://auth.purangpt.com/oidc/auth")!
    static let tokenEndpoint = URL(string: "https://auth.purangpt.com/oidc/token")!
    static let endSessionEndpoint = URL(string: "https://auth.purangpt.com/oidc/session/end")!

    // Dedicated Logto **Native** app (token_endpoint_auth_method=none → secretless
    // PKCE, so NO client secret ships in the IPA). Created via the Logto
    // Management API; redirect com.fcpuru95.purangpt://callback registered on it.
    // The old `t43ntgaztl5izt1h78lwc` is the web's confidential Traditional client
    // and must NOT be used here (it requires a secret at the token endpoint).
    static let appID = "gtiuhiw5zvl24uv4wc4us"

    /// The API the backend expects in the access token's audience. Backend
    /// API resource indicator. Set to nil — the web flow requests NO `resource`
    /// param (see src/app/api/logto/[action]/route.ts), and the backend does NOT
    /// enforce the token audience (auth.py: verify_aud defaults OFF unless
    /// ENFORCE_JWT_AUDIENCE is set). Requesting an unregistered resource like
    /// `https://api.purangpt.com` makes Logto reject the authorize call with
    /// `invalid_target` (verified against the live /oidc/auth endpoint). Match
    /// the working web flow: omit the resource entirely.
    static let apiResource: String? = nil

    /// Custom-scheme redirect registered for the native client in Logto.
    /// Mirrors the app's bundle id so it is guaranteed unique on-device.
    static let redirectURI = "com.fcpuru95.purangpt://callback"
    static let redirectScheme = "com.fcpuru95.purangpt"

    /// `offline_access` is required to receive a refresh token (the web app's
    /// known limitation is the ABSENCE of refresh — native fixes that here).
    static let scopes = "openid profile email offline_access"
}
