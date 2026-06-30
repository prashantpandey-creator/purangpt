#!/usr/bin/env swift
//
// Standalone parser test for the native SSE chat contract.
//
// Run:  swift test_sse_parse.swift
// Exits 0 on pass, non-zero (via fatalError) on any failed assertion.
//
// This is the Precondition-A test for `ChatEvent.parse`: it feeds the REAL
// captured backend output in `sse_fixture.txt` through the same frame-splitting
// + JSON-decoding logic the app uses, and asserts the reduced result. The parse
// body here is kept byte-identical to `ChatEvent.parse` in ChatModels.swift —
// if you change one, change both.

import Foundation

enum Ev: Equatable {
    case sources(Int)            // count, to keep the assertion simple
    case token(String)
    case status(String)
    case queryExpanded
    case done(String?)
    case unknown(String)
}

func parse(_ json: [String: Any]) -> Ev? {
    guard let type = json["type"] as? String else { return nil }
    switch type {
    case "token":   return .token(json["content"] as? String ?? "")
    case "status":  return .status(json["message"] as? String ?? "")
    case "sources": return .sources((json["sources"] as? [[String: Any]] ?? []).count)
    case "done":    return .done(json["session_id"] as? String)
    case "query_expanded": return .queryExpanded
    default:        return .unknown(type)
    }
}

func splitFrames(_ sse: String) -> [Ev] {
    var out: [Ev] = []
    for line in sse.split(separator: "\n", omittingEmptySubsequences: true) {
        let trimmed = line.trimmingCharacters(in: .whitespaces)
        guard trimmed.hasPrefix("data:") else { continue }
        let payload = String(trimmed.dropFirst("data:".count)).trimmingCharacters(in: .whitespaces)
        if payload.isEmpty || payload == "[DONE]" { continue }
        guard
            let data = payload.data(using: .utf8),
            let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
            let ev = parse(json)
        else { continue }
        out.append(ev)
    }
    return out
}

func assert(_ cond: Bool, _ msg: String) {
    if !cond { fatalError("ASSERT FAILED: \(msg)") }
}

// --- Load the real captured fixture beside this file ---
let here = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
let fixtureURL = here.appendingPathComponent("sse_fixture.txt")
let sse = try! String(contentsOf: fixtureURL, encoding: .utf8)

let events = splitFrames(sse)

// 1. Frame count: status, query_expanded, sources, token, token, done = 6
assert(events.count == 6, "expected 6 events, got \(events.count): \(events)")

// 2. First event is the search status, with emoji preserved.
if case .status(let m) = events[0] {
    assert(m.contains("Searching"), "status message wrong: \(m)")
} else { fatalError("event[0] not status: \(events[0])") }

// 3. query_expanded is recognized (and treated as a known-but-ignored event).
assert(events[1] == .queryExpanded, "event[1] not query_expanded: \(events[1])")

// 4. Sources frame decodes exactly one passage.
assert(events[2] == .sources(1), "expected 1 source, got \(events[2])")

// 5. Tokens accumulate to the full answer.
let tokens = events.compactMap { if case .token(let t) = $0 { return t } else { return nil } }
let answer = tokens.joined()
assert(answer == "Dharma is righteous duty.", "token reduction wrong: '\(answer)'")

// 6. done carries the session id, which the VM uses to thread the conversation.
assert(events.last == .done("abc123"), "done/session_id wrong: \(String(describing: events.last))")

// 7. SourceRef Codable decodes the real field names without throwing.
struct SourceRefT: Codable {
    let textId: String; let textName: String; let verseRange: String; let score: Double?
    enum CodingKeys: String, CodingKey {
        case textId = "text_id"; case textName = "text_name"
        case verseRange = "verse_range"; case score
    }
}
let srcLine = sse.split(separator: "\n").first { $0.contains("\"sources\"") }!
let srcPayload = String(srcLine.trimmingCharacters(in: .whitespaces).dropFirst("data:".count)).trimmingCharacters(in: .whitespaces)
let srcJSON = try! JSONSerialization.jsonObject(with: srcPayload.data(using: .utf8)!) as! [String: Any]
let firstSrc = (srcJSON["sources"] as! [[String: Any]])[0]
let srcData = try! JSONSerialization.data(withJSONObject: firstSrc)
let decoded = try! JSONDecoder().decode(SourceRefT.self, from: srcData)
assert(decoded.textName == "Mahabharata", "SourceRef decode wrong: \(decoded.textName)")
assert(decoded.verseRange == "42982", "SourceRef verse_range wrong: \(decoded.verseRange)")

print("✅ all SSE parser assertions passed (\(events.count) events, answer='\(answer)')")
