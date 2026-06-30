import Foundation

/// `AuthService` — the protocol-facing auth entry point for the native app.
///
/// It fulfils the web client's contract literally: the browser attaches a Bearer
/// token fetched from the app's **own** `/api/logto/token` endpoint plus a stable
/// `X-Device-ID` for guest tracking; the backend (`auth.py`) verifies the JWT and
/// lazily creates the `profiles` row. This service is the native mirror of that
/// path — useful when the app should ride the same `/api/logto/token` hop the web
/// uses (e.g. when the Logto SDK session lives in a Capacitor WebView cookie),
/// rather than driving the OIDC PKCE flow itself (which `AuthManager` already
/// does and which is the default native path per the project history).
///
/// Both `AuthService` and `AuthManager` conform to `AuthProviding`, so Chat /
/// Library / Store depend only on the protocol and the integrator can wire
/// whichever backing implementation is appropriate.
///
/// Design notes:
/// - Conforms to `AuthProviding`: `deviceID` + `currentToken()`.
/// - `currentToken()` returns the cached token while it is still valid, and only
///   hits `/api/logto/token` when missing/expired — so it is cheap on the hot
///   path of every outgoing request.
/// - Token validity is judged with the shared `JWT` helper (decode `exp`,
///   60s leeway). An opaque token is treated as valid until the endpoint reports
///   otherwise.
/// - The device id is the SAME `purangpt_device_id` used everywhere else
///   (`TokenStore.deviceID()`), so guest quota is consistent across the WebView
///   and native paths.
@MainActor
final class AuthService: ObservableObject, AuthProviding {

    // MARK: Published state (for SwiftUI binding)

    @Published private(set) var status: AuthStatus = .unknown

    // MARK: Stored

    /// Base URL of the Next.js app that exposes `/api/logto/token`. Defaults to
    /// the production frontend; override for local dev. (Distinct from the
    /// FastAPI backend base URL `ChatService` uses.)
    private let appBaseURL: URL

    /// Cached, in-memory access token + its absolute expiry. Source of truth is
    /// the server session behind `/api/logto/token`; we cache to avoid a network
    /// round-trip on every request.
    private var cachedToken: String?
    private var cachedExpiry: Date?

    /// Serialises concurrent `currentToken()` callers so only one fetch is in
    /// flight at a time (the others await the same task).
    private var inFlight: Task<String?, Never>?

    private let session: URLSession

    // MARK: AuthProviding

    /// Stable per-install id for guest tracking. Shared with the rest of the app.
    nonisolated var deviceID: String { TokenStore.deviceID() }

    /// A valid Bearer token, or `nil` for a guest. Refreshes transparently.
    func currentToken() async -> String? {
        if let token = cachedToken, let exp = cachedExpiry, Date().addingTimeInterval(60) < exp {
            return token
        }
        // Coalesce concurrent callers onto a single fetch.
        if let inFlight { return await inFlight.value }
        let task = Task<String?, Never> { [weak self] in
            await self?.fetchTokenFromEndpoint()
        }
        inFlight = task
        let result = await task.value
        inFlight = nil
        return result
    }

    // MARK: Init

    /// - Parameters:
    ///   - appBaseURL: origin serving `/api/logto/token`. Defaults to
    ///     `BackendAuthBaseURL` from Info.plist if present, else the production
    ///     frontend `https://purangpt.com`.
    init(appBaseURL: URL? = nil, session: URLSession = .shared) {
        self.appBaseURL = appBaseURL ?? Self.defaultAppBaseURL()
        self.session = session
    }

    private static func defaultAppBaseURL() -> URL {
        if let raw = Bundle.main.object(forInfoDictionaryKey: "AppAuthBaseURL") as? String,
           let url = URL(string: raw), !raw.isEmpty {
            return url
        }
        return URL(string: "https://purangpt.com")!
    }

    // MARK: Lifecycle

    /// Probe the session once at launch so the UI can show the right state. A
    /// guest (no server session) resolves to `.guest`, never an error.
    func restore() async {
        if let token = await currentToken() {
            status = .authenticated(AuthProfile.from(jwt: token))
        } else {
            status = .guest
        }
    }

    /// Drop the cached token and reflect guest state. Does NOT clear the
    /// server-side Logto session (that lives in the WebView / `/api/logto/sign-out`);
    /// the integrator should pair this with the web sign-out route when used.
    func signOut() {
        cachedToken = nil
        cachedExpiry = nil
        inFlight?.cancel()
        inFlight = nil
        status = .guest
    }

    // MARK: Token fetch (the /api/logto/token hop)

    /// GET `{appBaseURL}/api/logto/token`. The web route returns the current
    /// session's access token as JSON. Carries `X-Device-ID` so the server can
    /// correlate the request, and `Accept: application/json`. On any non-2xx or
    /// missing-token response we resolve to guest (no throw) — a guest having no
    /// token is the normal case, not an error.
    private func fetchTokenFromEndpoint() async -> String? {
        let url = appBaseURL.appendingPathComponent("/api/logto/token")
        var req = URLRequest(url: url)
        req.httpMethod = "GET"
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        req.setValue(deviceID, forHTTPHeaderField: "X-Device-ID")

        guard
            let (data, resp) = try? await session.data(for: req),
            let http = resp as? HTTPURLResponse
        else {
            updateStateForGuestIfNeeded()
            return nil
        }
        guard (200...299).contains(http.statusCode) else {
            // 401/403 => no server session => guest.
            updateStateForGuestIfNeeded()
            return nil
        }
        guard let token = Self.extractToken(from: data), !token.isEmpty else {
            updateStateForGuestIfNeeded()
            return nil
        }

        cachedToken = token
        cachedExpiry = JWT.expiry(token) ?? Date().addingTimeInterval(3600)
        status = .authenticated(AuthProfile.from(jwt: token))
        return token
    }

    private func updateStateForGuestIfNeeded() {
        cachedToken = nil
        cachedExpiry = nil
        if status != .guest { status = .guest }
    }

    /// Tolerant token extraction — the `/api/logto/token` route's JSON shape has
    /// varied (`{ "token": ... }` / `{ "accessToken": ... }` / `{ "access_token": ... }`),
    /// and some deployments return the raw token as plain text. Accept all.
    static func extractToken(from data: Data) -> String? {
        if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            for key in ["token", "accessToken", "access_token", "jwt"] {
                if let value = json[key] as? String, !value.isEmpty { return value }
            }
            // Nested `{ "data": { "token": ... } }`.
            if let nested = json["data"] as? [String: Any] {
                for key in ["token", "accessToken", "access_token", "jwt"] {
                    if let value = nested[key] as? String, !value.isEmpty { return value }
                }
            }
            return nil
        }
        // Plain-text token body (looks like a JWT: three dot-separated segments).
        if let raw = String(data: data, encoding: .utf8) {
            let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
                .trimmingCharacters(in: CharacterSet(charactersIn: "\""))
            if trimmed.split(separator: ".").count == 3 { return trimmed }
        }
        return nil
    }
}

// MARK: - AuthManager conforms to AuthProviding (retroactive)

/// Lets the existing OIDC-PKCE `AuthManager` satisfy the same protocol, so the
/// integrator can wire EITHER backing implementation into Chat/Library/Store
/// without those consumers knowing which. `AuthManager` already exposes
/// `tokenProvider()` (a `() async -> String?`); we adapt it to `currentToken()`,
/// and reuse the shared device id.
extension AuthManager: AuthProviding {
    nonisolated var deviceID: String { TokenStore.deviceID() }

    func currentToken() async -> String? {
        await tokenProvider()()
    }
}
