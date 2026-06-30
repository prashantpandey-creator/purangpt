import Foundation

// MARK: - AuthProviding

/// The single dependency the Chat (and Library / Store / History) modules need
/// from auth. They depend on THIS protocol, never on a concrete `AuthManager` /
/// `AuthService` — so the token transport (direct Logto OIDC vs the Next.js
/// `/api/logto/token` hop) can change without touching any consumer.
///
/// The outgoing-request contract is exactly the web client's:
///   - attach `Authorization: Bearer <token>` from `currentToken()` when present,
///   - attach `X-Device-ID: <deviceID>` always, for guest quota tracking.
/// `ChatService` already takes `deviceID: String` + `tokenProvider: () async -> String?`;
/// `tokenProviderClosure()` below adapts any `AuthProviding` to that exact shape.
protocol AuthProviding: AnyObject {
    /// A stable per-install identifier for guest quota tracking. Mirrors the
    /// web's `purangpt_device_id` (localStorage). Always available — even for a
    /// signed-out guest — so it is a non-optional, synchronous property.
    var deviceID: String { get }

    /// A *valid* (non-expired, transparently-refreshed) Logto access token, or
    /// `nil` when the user is a guest / no session can be obtained. Implementations
    /// must refresh on demand so the backend never sees an expired Bearer.
    func currentToken() async -> String?
}

extension AuthProviding {
    /// Adapts this provider to the `() async -> String?` closure that
    /// `ChatService`, `LibraryService`, and `NativeStore` already accept. Captures
    /// `self` weakly so the closure never keeps the provider alive.
    func tokenProviderClosure() -> () async -> String? {
        { [weak self] in await self?.currentToken() }
    }
}

// MARK: - Auth value types

/// The authenticated user's lightweight profile, decoded from the ID/access
/// token claims (never trusted for authorization — the backend verifies the JWT
/// and lazily creates the `profiles` row). Distinct from the persisted
/// `TokenSet` (Keychain wire shape) on purpose: this is the UI-facing view.
struct AuthProfile: Equatable, Codable {
    var subject: String?
    var email: String?
    var name: String?
    var picture: String?

    var isEmpty: Bool { subject == nil && email == nil && name == nil }

    /// Best-effort profile from a JWT's payload claims. Returns an empty profile
    /// for an opaque (non-JWT) token rather than failing.
    static func from(jwt token: String?) -> AuthProfile {
        guard let token, let claims = JWT.decodePayload(token) else { return AuthProfile() }
        return AuthProfile(
            subject: claims["sub"] as? String,
            email: claims["email"] as? String,
            name: (claims["name"] as? String) ?? (claims["username"] as? String),
            picture: claims["picture"] as? String
        )
    }
}

/// Coarse auth state for driving UI (sign-in button, paywall gating). Kept
/// separate from `AuthManager.State` so consumers binding to `AuthService` don't
/// import the OIDC-flow type.
enum AuthStatus: Equatable {
    case unknown                       // before first restore
    case guest                         // no valid session — chat works under guest quota
    case authenticated(AuthProfile)

    var isAuthenticated: Bool {
        if case .authenticated = self { return true }
        return false
    }

    var profile: AuthProfile? {
        if case let .authenticated(p) = self { return p }
        return nil
    }
}

/// Errors surfaced by `AuthService`. Expected, non-fatal failures (user cancel,
/// guest with no session) are NOT errors — they resolve to `.guest`.
enum AuthServiceError: Error, Equatable {
    case noAuthorizationCode
    case stateMismatch
    case tokenEndpointFailed(status: Int)
    case malformedTokenResponse
    case notConfigured
}
