#!/usr/bin/env swift
//
// Deterministic tests for the native auth primitives: PKCE S256 and JWT decode.
// Run:  swift test_auth.swift   (exits 0 on pass, fatalError on failure)
//
// The PKCE vector is the canonical example from RFC 7636 Appendix B, so this
// proves our base64url + SHA256 path is correct against the spec — not just
// internally consistent.

import Foundation
import CryptoKit

func base64URL(_ data: Data) -> String {
    data.base64EncodedString()
        .replacingOccurrences(of: "+", with: "-")
        .replacingOccurrences(of: "/", with: "_")
        .replacingOccurrences(of: "=", with: "")
}

func challenge(for verifier: String) -> String {
    base64URL(Data(SHA256.hash(data: Data(verifier.utf8))))
}

func decodePayload(_ token: String) -> [String: Any]? {
    let segs = token.split(separator: ".")
    guard segs.count == 3 else { return nil }
    var b64 = String(segs[1])
        .replacingOccurrences(of: "-", with: "+")
        .replacingOccurrences(of: "_", with: "/")
    while b64.count % 4 != 0 { b64 += "=" }
    guard let data = Data(base64Encoded: b64),
          let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
    else { return nil }
    return json
}

func expiry(_ token: String) -> Date? {
    guard let exp = decodePayload(token)?["exp"] as? Double else { return nil }
    return Date(timeIntervalSince1970: exp)
}

func isExpired(_ token: String, leeway: TimeInterval = 60) -> Bool {
    guard let exp = expiry(token) else { return false }
    return Date().addingTimeInterval(leeway) >= exp
}

func assert(_ cond: Bool, _ msg: String) {
    if !cond { fatalError("ASSERT FAILED: \(msg)") }
}

// 1. RFC 7636 Appendix B canonical PKCE vector.
let rfcVerifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
let rfcChallenge = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
assert(challenge(for: rfcVerifier) == rfcChallenge,
       "PKCE S256 challenge mismatch: got \(challenge(for: rfcVerifier))")

// 2. JWT payload decode — handcraft a token with exp far in the future.
//    header.payload.sig where payload = {"email":"x@y.com","exp":<future>}
func b64urlEncode(_ s: String) -> String {
    base64URL(Data(s.utf8))
}
let future = Date().addingTimeInterval(3600).timeIntervalSince1970
let header = b64urlEncode("{\"alg\":\"RS256\",\"typ\":\"JWT\"}")
let payload = b64urlEncode("{\"email\":\"daddy@purangpt.com\",\"exp\":\(Int(future))}")
let jwt = "\(header).\(payload).fakesig"

assert(decodePayload(jwt)?["email"] as? String == "daddy@purangpt.com",
       "JWT email claim not decoded")
assert(isExpired(jwt) == false, "future-exp JWT wrongly flagged expired")

// 3. Expired token is detected.
let past = Date().addingTimeInterval(-10).timeIntervalSince1970
let expiredPayload = b64urlEncode("{\"exp\":\(Int(past))}")
let expiredJWT = "\(header).\(expiredPayload).sig"
assert(isExpired(expiredJWT) == true, "past-exp JWT not flagged expired")

// 4. Opaque (non-JWT) Google token: two segments → decode nil → treated as valid.
let opaque = "ya29.someopaquegoogletoken"
assert(decodePayload(opaque) == nil, "opaque token should not decode as JWT")
assert(isExpired(opaque) == false, "opaque token must be treated as valid (backend verifies)")

print("✅ all auth assertions passed (PKCE RFC vector + JWT decode/expiry)")
