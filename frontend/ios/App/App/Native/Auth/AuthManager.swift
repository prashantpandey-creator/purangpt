import Foundation
import AuthenticationServices

/// Drives native Logto authentication: Authorization Code + PKCE via
/// `ASWebAuthenticationSession`, token persistence in the Keychain, and
/// proactive refresh. Exposes a `tokenProvider` closure that `ChatService`
/// consumes — so the native chat authenticates real users, not just guests.
@MainActor
final class AuthManager: NSObject, ObservableObject {
    enum State: Equatable {
        case unknown          // before first restore
        case guest            // no valid session — chat works under guest quota
        case authenticated(email: String?)
    }

    @Published private(set) var state: State = .unknown

    private var current: TokenSet?
    private var session: ASWebAuthenticationSession?

    /// Raw nonce for an in-flight Sign in with Apple (set in `prepareAppleRequest`,
    /// forwarded to the backend in `handleAppleCompletion`). See AppleSignIn.swift.
    var pendingAppleNonce: String?

    /// Restore any persisted session at launch. If the access token is expired
    /// but a refresh token exists, refresh silently.
    func restore() async {
        guard let set = TokenStore.load() else { state = .guest; return }
        current = set
        if JWT.isExpired(set.accessToken), set.refreshToken != nil {
            await refreshIfPossible()
        } else {
            state = .authenticated(email: emailFrom(set))
        }
    }

    /// The token closure handed to `ChatService`. Refreshes on demand so the
    /// backend never sees an expired Bearer.
    func tokenProvider() -> () async -> String? {
        { [weak self] in
            guard let self else { return nil }
            return await self.validAccessToken()
        }
    }

    private func validAccessToken() async -> String? {
        guard let set = current else { return nil }
        if JWT.isExpired(set.accessToken) {
            await refreshIfPossible()
        }
        return current?.accessToken
    }

    // MARK: - Login

    func signIn() async {
        let verifier = PKCE.makeVerifier()
        let challenge = PKCE.challenge(for: verifier)
        let stateParam = PKCE.randomState()

        var comps = URLComponents(url: AuthConfig.authorizationEndpoint, resolvingAgainstBaseURL: false)!
        var items: [URLQueryItem] = [
            .init(name: "client_id", value: AuthConfig.appID),
            .init(name: "redirect_uri", value: AuthConfig.redirectURI),
            .init(name: "response_type", value: "code"),
            .init(name: "scope", value: AuthConfig.scopes),
            .init(name: "prompt", value: "consent"),
            .init(name: "code_challenge", value: challenge),
            .init(name: "code_challenge_method", value: "S256"),
            .init(name: "state", value: stateParam),
        ]
        if let resource = AuthConfig.apiResource {
            items.append(.init(name: "resource", value: resource))
        }
        comps.queryItems = items
        guard let authURL = comps.url else { return }

        let code: String
        do {
            code = try await presentWebAuth(authURL: authURL, expectedState: stateParam)
        } catch {
            // user cancelled or flow failed — stay guest
            return
        }
        await exchange(code: code, verifier: verifier)
    }

    private func presentWebAuth(authURL: URL, expectedState: String) async throws -> String {
        try await withCheckedThrowingContinuation { cont in
            let s = ASWebAuthenticationSession(
                url: authURL,
                callbackURLScheme: AuthConfig.redirectScheme
            ) { callback, error in
                if let error { cont.resume(throwing: error); return }
                guard
                    let callback,
                    let items = URLComponents(url: callback, resolvingAgainstBaseURL: false)?.queryItems,
                    let code = items.first(where: { $0.name == "code" })?.value
                else {
                    cont.resume(throwing: AuthError.noCode); return
                }
                let returnedState = items.first(where: { $0.name == "state" })?.value
                guard returnedState == expectedState else {
                    cont.resume(throwing: AuthError.stateMismatch); return
                }
                cont.resume(returning: code)
            }
            s.presentationContextProvider = self
            s.prefersEphemeralWebBrowserSession = false
            self.session = s
            s.start()
        }
    }

    // MARK: - Token exchange & refresh

    private func exchange(code: String, verifier: String) async {
        var body = URLComponents()
        var items: [URLQueryItem] = [
            .init(name: "grant_type", value: "authorization_code"),
            .init(name: "code", value: code),
            .init(name: "redirect_uri", value: AuthConfig.redirectURI),
            .init(name: "client_id", value: AuthConfig.appID),
            .init(name: "code_verifier", value: verifier),
        ]
        if let resource = AuthConfig.apiResource {
            items.append(.init(name: "resource", value: resource))
        }
        body.queryItems = items
        if let set = await postToken(body.query ?? "") {
            persist(set)
        }
    }

    private func refreshIfPossible() async {
        guard let refresh = current?.refreshToken else { state = .guest; return }
        var body = URLComponents()
        var items: [URLQueryItem] = [
            .init(name: "grant_type", value: "refresh_token"),
            .init(name: "refresh_token", value: refresh),
            .init(name: "client_id", value: AuthConfig.appID),
        ]
        if let resource = AuthConfig.apiResource {
            items.append(.init(name: "resource", value: resource))
        }
        body.queryItems = items
        if let set = await postToken(body.query ?? "") {
            persist(set)
        } else {
            // refresh failed — drop to guest, force re-login
            TokenStore.clear()
            current = nil
            state = .guest
        }
    }

    private func postToken(_ form: String) async -> TokenSet? {
        var req = URLRequest(url: AuthConfig.tokenEndpoint)
        req.httpMethod = "POST"
        req.setValue("application/x-www-form-urlencoded", forHTTPHeaderField: "Content-Type")
        req.httpBody = form.data(using: .utf8)
        guard
            let (data, resp) = try? await URLSession.shared.data(for: req),
            let http = resp as? HTTPURLResponse, (200...299).contains(http.statusCode),
            let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let access = json["access_token"] as? String
        else { return nil }

        let expiresIn = (json["expires_in"] as? Double) ?? 3600
        // Prefer the JWT's own exp when present; fall back to expires_in.
        let exp = JWT.expiry(access)?.timeIntervalSince1970
            ?? Date().addingTimeInterval(expiresIn).timeIntervalSince1970
        return TokenSet(
            accessToken: access,
            refreshToken: (json["refresh_token"] as? String) ?? current?.refreshToken,
            idToken: json["id_token"] as? String,
            expiresAt: exp
        )
    }

    private func persist(_ set: TokenSet) {
        current = set
        TokenStore.save(set)
        state = .authenticated(email: emailFrom(set))
    }

    /// Adopt an externally-obtained session (native Sign in with Apple → our
    /// `/api/auth/apple`). Installs the token set + reflects authenticated state.
    /// Lives here (not the Apple extension) because `persist` is file-private.
    func adoptSession(_ set: TokenSet) {
        persist(set)
    }

    /// Backend (FastAPI) base URL for the `/api/auth/apple` hop. Mirrors
    /// RootView's resolver: Info.plist `BackendBaseURL`, else production.
    var appleBackendBaseURL: URL {
        if let s = Bundle.main.object(forInfoDictionaryKey: "BackendBaseURL") as? String,
           let u = URL(string: s) { return u }
        return URL(string: "https://purangpt.com")!
    }

    func signOut() {
        TokenStore.clear()
        current = nil
        state = .guest
    }

    private func emailFrom(_ set: TokenSet) -> String? {
        if let id = set.idToken, let email = JWT.decodePayload(id)?["email"] as? String { return email }
        return JWT.decodePayload(set.accessToken)?["email"] as? String
    }

    enum AuthError: Error { case noCode, stateMismatch }
}

extension AuthManager: ASWebAuthenticationPresentationContextProviding {
    func presentationAnchor(for session: ASWebAuthenticationSession) -> ASPresentationAnchor {
        // Front-most window on iOS 15+.
        UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .flatMap { $0.windows }
            .first { $0.isKeyWindow } ?? ASPresentationAnchor()
    }
}
