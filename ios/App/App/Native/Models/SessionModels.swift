import Foundation

// MARK: - Chat session wire models
//
// Mirror the live backend (confirmed against source + prod):
//   GET    /api/sessions            -> { sessions: [SessionSummary] }
//   GET    /api/session/{id}        -> { session_id, message_count, history: [HistoryMessage] }
//   DELETE /api/session/{id}        -> { cleared: true }
// Sessions are keyed server-side by logto_user_id OR guest_id (X-Device-ID), so
// even a signed-out user gets per-device history.

/// One row in the session list (`session_manager.get_all_sessions`).
struct SessionSummary: Codable, Identifiable, Hashable {
    let id: String
    let title: String
    let updatedAt: Double

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case updatedAt = "updated_at"
    }
}

/// One persisted message in a session's history. The DB stores a raw JSON array;
/// decode leniently — only role + content are guaranteed; sources may be absent.
struct HistoryMessage: Codable, Hashable {
    let role: String
    let content: String
    let sources: [SourceRef]?
}

/// The full history payload for a session (`/api/session/{id}`).
struct SessionHistory: Codable, Hashable {
    let sessionId: String
    let messageCount: Int
    let history: [HistoryMessage]

    enum CodingKeys: String, CodingKey {
        case sessionId = "session_id"
        case messageCount = "message_count"
        case history
    }
}
