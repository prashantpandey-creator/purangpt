import Foundation
import AuthenticationServices
import CryptoKit
import os

/// Native Sign in with Apple — the system ASAuthorization (Face ID) sheet.
///
/// The official SwiftUI `SignInWithAppleButton` (see `SignInView`) presents the
/// sheet; this file carries the nonce plumbing and the backend hand-off. The app
/// obtains the Apple identity token natively (audience = the app's BUNDLE ID, so
/// NO Services ID and NO Sign-in-with-Apple key are needed), then POSTs it to the
/// backend `/api/auth/apple`, which verifies it against Apple's public keys and
/// returns a first-party session token we persist like any other (`TokenStore`).
enum AppleNonce {
    /// A cryptographically-random nonce. The RAW value is sent to the backend;
    /// only its SHA256 is handed to Apple, so a stolen identity token cannot be
    /// replayed without the matching raw nonce.
    static func random(_ length: Int = 32) -> String {
        let charset: [Character] =
            Array("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-._")
        var result = ""
        var remaining = length
        while remaining > 0 {
            var randoms = [UInt8](repeating: 0, count: 16)
            _ = SecRandomCopyBytes(kSecRandomDefault, randoms.count, &randoms)
            for r in randoms where remaining > 0 {
                result.append(charset[Int(r) % charset.count])
                remaining -= 1
            }
        }
        return result
    }

    /// SHA256 hex of the raw nonce — the value handed to ASAuthorization. Apple
    /// echoes it into the id_token's `nonce` claim; the backend re-derives it.
    static func sha256Hex(_ input: String) -> String {
        SHA256.hash(data: Data(input.utf8)).map { String(format: "%02x", $0) }.joined()
    }
}

extension AuthManager {
    private static let appleLog = Logger(subsystem: "com.fcpuru95.purangpt", category: "AppleSignIn")

    /// Configure the ASAuthorization request: scopes + the hashed nonce. Stores
    /// the raw nonce so `handleAppleCompletion` can forward it to the backend.
    func prepareAppleRequest(_ request: ASAuthorizationAppleIDRequest) {
        let raw = AppleNonce.random()
        pendingAppleNonce = raw
        request.requestedScopes = [.fullName, .email]
        request.nonce = AppleNonce.sha256Hex(raw)
    }

    /// Handle the `SignInWithAppleButton` completion. On success verify with the
    /// backend and persist a session; on cancel/failure stay guest (never crash).
    func handleAppleCompletion(_ result: Result<ASAuthorization, Error>) async {
        switch result {
        case .failure(let error):
            Self.appleLog.info("Apple sign-in cancelled/failed: \(error.localizedDescription, privacy: .public)")
        case .success(let authorization):
            guard
                let cred = authorization.credential as? ASAuthorizationAppleIDCredential,
                let tokenData = cred.identityToken,
                let identityToken = String(data: tokenData, encoding: .utf8)
            else {
                Self.appleLog.error("Apple sign-in: missing identity token in credential")
                return
            }
            let raw = pendingAppleNonce ?? ""
            pendingAppleNonce = nil
            let formatted = cred.fullName.map { PersonNameComponentsFormatter().string(from: $0) }
            let name = formatted?.trimmingCharacters(in: .whitespacesAndNewlines)
            await completeAppleSignIn(
                identityToken: identityToken,
                rawNonce: raw,
                fullName: (name?.isEmpty == false) ? name : nil,
                email: cred.email
            )
        }
    }

    /// POST the Apple identity token to `/api/auth/apple`; adopt the returned
    /// first-party session token. Failure leaves the user a guest (no throw).
    func completeAppleSignIn(identityToken: String, rawNonce: String,
                             fullName: String?, email: String?) async {
        var payload: [String: Any] = ["identity_token": identityToken]
        if !rawNonce.isEmpty { payload["nonce"] = rawNonce }
        if let fullName { payload["full_name"] = fullName }
        if let email { payload["email"] = email }

        let url = appleBackendBaseURL.appendingPathComponent("/api/auth/apple")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        req.httpBody = try? JSONSerialization.data(withJSONObject: payload)

        guard
            let (data, resp) = try? await URLSession.shared.data(for: req),
            let http = resp as? HTTPURLResponse, (200...299).contains(http.statusCode),
            let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let token = json["token"] as? String, !token.isEmpty
        else {
            Self.appleLog.error("Apple sign-in: /api/auth/apple did not return a session token")
            return
        }

        let expiresIn = (json["expires_in"] as? Double) ?? (30 * 24 * 3600)
        // Prefer the session JWT's own exp; fall back to expires_in.
        let exp = JWT.expiry(token)?.timeIntervalSince1970
            ?? Date().addingTimeInterval(expiresIn).timeIntervalSince1970
        let set = TokenSet(accessToken: token, refreshToken: nil, idToken: nil, expiresAt: exp)
        adoptSession(set)   // installs token + flips state to .authenticated
        Self.appleLog.info("Apple sign-in: session adopted (valid ~\(Int(expiresIn))s)")
    }
}
