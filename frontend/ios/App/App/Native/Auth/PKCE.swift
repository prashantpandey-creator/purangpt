import Foundation
import CryptoKit

/// PKCE (RFC 7636) helpers for the Authorization Code flow. Pure, deterministic
/// functions — covered by test_auth.swift.
enum PKCE {
    /// A high-entropy code verifier: 32 random bytes, base64url, no padding.
    static func makeVerifier() -> String {
        var bytes = [UInt8](repeating: 0, count: 32)
        _ = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        return base64URL(Data(bytes))
    }

    /// The S256 challenge: base64url(SHA256(verifier)).
    static func challenge(for verifier: String) -> String {
        let digest = SHA256.hash(data: Data(verifier.utf8))
        return base64URL(Data(digest))
    }

    /// A random state/nonce value for CSRF protection on the redirect.
    static func randomState() -> String {
        var bytes = [UInt8](repeating: 0, count: 16)
        _ = SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes)
        return base64URL(Data(bytes))
    }

    static func base64URL(_ data: Data) -> String {
        data.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }
}

/// Minimal JWT helpers — decode the payload to read `exp` for proactive refresh.
/// We do NOT verify the signature on-device; the backend does that. This is only
/// used to decide *when* to refresh, never to trust claims for authorization.
enum JWT {
    /// Decode the payload segment of a JWT into a dictionary. Returns nil if the
    /// token isn't a well-formed three-segment JWT (e.g. an opaque Google token).
    static func decodePayload(_ token: String) -> [String: Any]? {
        let segments = token.split(separator: ".")
        guard segments.count == 3 else { return nil }
        var b64 = String(segments[1])
            .replacingOccurrences(of: "-", with: "+")
            .replacingOccurrences(of: "_", with: "/")
        // Re-pad to a multiple of 4 for the base64 decoder.
        while b64.count % 4 != 0 { b64 += "=" }
        guard
            let data = Data(base64Encoded: b64),
            let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else { return nil }
        return json
    }

    /// Unix expiry of the token, if present.
    static func expiry(_ token: String) -> Date? {
        guard let exp = decodePayload(token)?["exp"] as? Double else { return nil }
        return Date(timeIntervalSince1970: exp)
    }

    /// Whether the token is expired (or expires within `leeway` seconds).
    static func isExpired(_ token: String, leeway: TimeInterval = 60) -> Bool {
        guard let exp = expiry(token) else { return false } // opaque token: assume valid
        return Date().addingTimeInterval(leeway) >= exp
    }
}
