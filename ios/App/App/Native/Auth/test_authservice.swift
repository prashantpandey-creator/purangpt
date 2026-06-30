#!/usr/bin/env swift
//
// Deterministic tests for AuthService's pure token-parsing + profile-decoding
// logic. Run:  swift test_authservice.swift   (exits 0 on pass, fatalError on
// failure). Self-contained like test_auth.swift — it re-implements the logic
// under test so it runs without the app module; keep it in sync with
// AuthService.extractToken / AuthProfile.from(jwt:) if either changes.
//

import Foundation

// MARK: - logic under test (mirror of AuthService.extractToken)

func extractToken(from data: Data) -> String? {
    if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
        for key in ["token", "accessToken", "access_token", "jwt"] {
            if let value = json[key] as? String, !value.isEmpty { return value }
        }
        if let nested = json["data"] as? [String: Any] {
            for key in ["token", "accessToken", "access_token", "jwt"] {
                if let value = nested[key] as? String, !value.isEmpty { return value }
            }
        }
        return nil
    }
    if let raw = String(data: data, encoding: .utf8) {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "\""))
        if trimmed.split(separator: ".").count == 3 { return trimmed }
    }
    return nil
}

// MARK: - logic under test (mirror of JWT.decodePayload / AuthProfile.from)

func decodePayload(_ token: String) -> [String: Any]? {
    let segments = token.split(separator: ".")
    guard segments.count == 3 else { return nil }
    var b64 = String(segments[1])
        .replacingOccurrences(of: "-", with: "+")
        .replacingOccurrences(of: "_", with: "/")
    while b64.count % 4 != 0 { b64 += "=" }
    guard let data = Data(base64Encoded: b64),
          let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
    else { return nil }
    return json
}

func base64URL(_ data: Data) -> String {
    data.base64EncodedString()
        .replacingOccurrences(of: "+", with: "-")
        .replacingOccurrences(of: "/", with: "_")
        .replacingOccurrences(of: "=", with: "")
}

/// Build a (signature-less) JWT with the given claims for testing the decoder.
func makeJWT(_ claims: [String: Any]) -> String {
    let header = base64URL(try! JSONSerialization.data(withJSONObject: ["alg": "none", "typ": "JWT"]))
    let payload = base64URL(try! JSONSerialization.data(withJSONObject: claims))
    return "\(header).\(payload).sig"
}

func check(_ cond: Bool, _ msg: String) {
    if !cond { fatalError("FAIL: \(msg)") }
}

func d(_ s: String) -> Data { Data(s.utf8) }

// MARK: - extractToken cases

// 1. { "token": ... }
check(extractToken(from: d(#"{"token":"a.b.c"}"#)) == "a.b.c", "token key")
// 2. { "accessToken": ... }
check(extractToken(from: d(#"{"accessToken":"x.y.z"}"#)) == "x.y.z", "accessToken key")
// 3. { "access_token": ... }
check(extractToken(from: d(#"{"access_token":"p.q.r"}"#)) == "p.q.r", "access_token key")
// 4. nested { "data": { "token": ... } }
check(extractToken(from: d(#"{"data":{"token":"n.e.s"}}"#)) == "n.e.s", "nested data.token")
// 5. plain-text JWT body
check(extractToken(from: d("aaa.bbb.ccc")) == "aaa.bbb.ccc", "plain-text jwt")
// 6. quoted plain-text JWT body
check(extractToken(from: d("\"aaa.bbb.ccc\"")) == "aaa.bbb.ccc", "quoted plain-text jwt")
// 7. empty token value -> nil
check(extractToken(from: d(#"{"token":""}"#)) == nil, "empty token -> nil")
// 8. no token at all -> nil (guest)
check(extractToken(from: d(#"{"error":"unauthorized"}"#)) == nil, "no token -> nil")
// 9. non-JSON, non-JWT -> nil
check(extractToken(from: d("not a token")) == nil, "garbage -> nil")
// 10. key priority: token wins over access_token
check(extractToken(from: d(#"{"access_token":"second","token":"first"}"#)) == "first", "token priority")

// MARK: - AuthProfile.from(jwt:) cases

let jwt = makeJWT(["sub": "usr_123", "email": "seeker@purangpt.com", "name": "Seeker"])
let claims = decodePayload(jwt)
check(claims?["sub"] as? String == "usr_123", "decode sub")
check(claims?["email"] as? String == "seeker@purangpt.com", "decode email")
check(claims?["name"] as? String == "Seeker", "decode name")

// opaque (non-JWT) token -> nil payload -> empty profile, never a crash
check(decodePayload("opaque-google-token") == nil, "opaque token -> nil payload")

// username falls back when name absent (mirrors AuthProfile.from)
let jwt2 = makeJWT(["sub": "u2", "username": "vyasa"])
let claims2 = decodePayload(jwt2)
let name2 = (claims2?["name"] as? String) ?? (claims2?["username"] as? String)
check(name2 == "vyasa", "username fallback for name")

print("test_authservice: ALL PASS")
