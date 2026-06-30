import Foundation

// MARK: - Wire models (mirror src/lib/api.ts exactly)
//
// These types are the Swift mirror of the TypeScript contract in
// `src/lib/api.ts`. The FastAPI backend (`purangpt/backend/main.py`) emits SSE
// frames of the form `data: {json}\n\n`, where each JSON object carries a
// `type` discriminator. Keep this file in sync with `ChatEvent` in api.ts —
// if a new event type is added on either side, add it here too.

/// A source passage returned by the backend (`SourceRef` in api.ts /
/// `to_frontend_dict` in the backend).
struct SourceRef: Codable, Identifiable, Hashable {
    var id: String { chunkId ?? "\(textId)-\(reference)" }

    let textId: String
    let chunkId: String?
    let textName: String
    let purana: String
    let reference: String
    let verseRange: String
    let text: String
    let language: String
    let edition: String?
    let tradition: String?
    let score: Double?

    enum CodingKeys: String, CodingKey {
        case textId = "text_id"
        case chunkId = "chunk_id"
        case textName = "text_name"
        case purana
        case reference
        case verseRange = "verse_range"
        case text
        case language
        case edition
        case tradition
        case score
    }
}

/// The discrete SSE events emitted by `/api/chat`. Mirrors the `ChatEvent`
/// discriminated union in api.ts. Unknown event types decode to `.unknown`
/// rather than throwing, so a backend addition never crashes the stream.
enum ChatEvent {
    case sources([SourceRef])
    case token(String)
    case reasoning(String)
    case status(String)
    case error(String)
    case visual(String)
    case done(sessionId: String?)
    case unknown(type: String)

    /// Parse a single decoded JSON object (the payload after `data: `).
    static func parse(_ json: [String: Any]) -> ChatEvent? {
        guard let type = json["type"] as? String else { return nil }
        switch type {
        case "token":
            return .token(json["content"] as? String ?? "")
        case "reasoning":
            return .reasoning(json["content"] as? String ?? "")
        case "status":
            return .status(json["message"] as? String ?? "")
        case "error":
            return .error(json["message"] as? String ?? "Unknown error")
        case "visual":
            return .visual(json["form"] as? String ?? "")
        case "sources":
            let raw = json["sources"] as? [[String: Any]] ?? []
            let decoded: [SourceRef] = raw.compactMap { dict in
                guard let data = try? JSONSerialization.data(withJSONObject: dict) else { return nil }
                return try? JSONDecoder().decode(SourceRef.self, from: data)
            }
            return .sources(decoded)
        case "done":
            return .done(sessionId: json["session_id"] as? String)
        case "query_expanded":
            // Metadata event the native chat UI does not yet surface; ignore safely.
            return .unknown(type: type)
        default:
            return .unknown(type: type)
        }
    }
}

/// Query mode. The new native UI only ever sends `.chat` or `.deep`; the
/// `guide`/`research` aliases the backend resolves are intentionally omitted.
enum QueryMode: String {
    case chat
    case deep
}

/// A message in the chat transcript (mirrors `ChatMessage`).
struct ChatMessageVM: Identifiable, Equatable {
    let id: String
    let role: Role
    var content: String
    var sources: [SourceRef]
    var reasoning: String?
    var pending: Bool
    var error: Bool

    enum Role: String { case user, assistant }

    static func user(_ text: String) -> ChatMessageVM {
        ChatMessageVM(id: UUID().uuidString, role: .user, content: text,
                      sources: [], reasoning: nil, pending: false, error: false)
    }

    static func assistantPending() -> ChatMessageVM {
        ChatMessageVM(id: UUID().uuidString, role: .assistant, content: "",
                      sources: [], reasoning: nil, pending: true, error: false)
    }
}

/// Thrown when the backend returns 429 (free quota exhausted). Callers detect
/// this to trigger the upgrade paywall instead of a transient-error retry.
struct LimitReachedError: Error {
    let message: String
}
