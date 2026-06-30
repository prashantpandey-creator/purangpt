import Foundation

/// Native streaming client for the FastAPI `/api/chat` SSE endpoint.
///
/// This is the Swift equivalent of `streamChat` in `src/lib/api.ts`. It talks
/// to the backend **directly** (not through the Next.js API routes), per the
/// chosen architecture. Auth is a Bearer token (Logto JWT or Google
/// access_token — the backend accepts both, see `backend/auth.py`) plus an
/// `X-Device-ID` header for guest tracking.
///
/// Frames arrive as `data: {json}\n\n`; we split on newlines, strip the
/// `data: ` prefix, decode JSON, and emit typed `ChatEvent`s.
actor ChatService {

    /// Base URL of the FastAPI backend, e.g. https://purangpt.com.
    private let baseURL: URL
    /// Supplies the current auth token (nil ⇒ guest). Async so it can refresh.
    private let tokenProvider: () async -> String?
    /// Stable per-install device id for guest quota tracking.
    private let deviceID: String

    private let CONNECT_TIMEOUT: TimeInterval = 15
    private let IDLE_TIMEOUT: TimeInterval = 45

    init(baseURL: URL,
         deviceID: String,
         tokenProvider: @escaping () async -> String?) {
        self.baseURL = baseURL
        self.deviceID = deviceID
        self.tokenProvider = tokenProvider
    }

    struct Request {
        var query: String
        var mode: QueryMode = .chat
        var sessionID: String = "default"
        var topK: Int = 10
        var model: String = "auto"
        var language: String = "en"
    }

    /// Stream a chat completion. Throws `LimitReachedError` on 429 so the
    /// caller can show the paywall instead of a retry prompt.
    func stream(_ req: Request) -> AsyncThrowingStream<ChatEvent, Error> {
        AsyncThrowingStream { continuation in
            let task = Task {
                do {
                    try await self.run(req, into: continuation)
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
            continuation.onTermination = { _ in task.cancel() }
        }
    }

    private func run(_ req: Request,
                     into continuation: AsyncThrowingStream<ChatEvent, Error>.Continuation) async throws {
        var urlReq = URLRequest(url: baseURL.appendingPathComponent("/api/chat"))
        urlReq.httpMethod = "POST"
        urlReq.timeoutInterval = CONNECT_TIMEOUT
        urlReq.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlReq.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        urlReq.setValue(deviceID, forHTTPHeaderField: "X-Device-ID")
        if let token = await tokenProvider() {
            urlReq.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        // Belt-and-braces language directive, matching api.ts behaviour.
        let langNames = ["en": "English", "hi": "Hindi", "ru": "Russian"]
        let directive = (req.language != "en")
            ? (langNames[req.language].map { "Please respond entirely in \($0).\n\n" } ?? "")
            : ""

        let body: [String: Any] = [
            "query": directive + req.query,
            "mode": req.mode.rawValue,
            "session_id": req.sessionID,
            "top_k": req.topK,
            "model": req.model,
            "language": req.language,
            "stream": true,
        ]
        urlReq.httpBody = try JSONSerialization.data(withJSONObject: body)

        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = IDLE_TIMEOUT
        let session = URLSession(configuration: config)

        let (bytes, response): (URLSession.AsyncBytes, URLResponse)
        do {
            (bytes, response) = try await session.bytes(for: urlReq)
        } catch {
            throw mapTransportError(error)
        }

        guard let http = response as? HTTPURLResponse else {
            throw NSError(domain: "ChatService", code: -1,
                          userInfo: [NSLocalizedDescriptionKey: "No response from server."])
        }

        if http.statusCode == 429 {
            throw LimitReachedError(message: "You've reached your free message limit. Upgrade to Pro for unlimited access.")
        }
        guard (200...299).contains(http.statusCode) else {
            throw NSError(domain: "ChatService", code: http.statusCode,
                          userInfo: [NSLocalizedDescriptionKey: "Request failed (\(http.statusCode))."])
        }

        // Parse SSE frames line-by-line. A frame is one or more `data:` lines
        // terminated by a blank line; the backend emits one JSON object per
        // `data:` line, so we can decode each line independently.
        for try await line in bytes.lines {
            if Task.isCancelled { return }
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            guard trimmed.hasPrefix("data:") else { continue }

            let payload = String(trimmed.dropFirst("data:".count))
                .trimmingCharacters(in: .whitespaces)
            if payload.isEmpty || payload == "[DONE]" { continue }

            guard
                let data = payload.data(using: .utf8),
                let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                let event = ChatEvent.parse(json)
            else { continue }

            continuation.yield(event)
            if case .done = event { return }
        }
    }

    private func mapTransportError(_ error: Error) -> Error {
        let ns = error as NSError
        if ns.domain == NSURLErrorDomain && ns.code == NSURLErrorTimedOut {
            return NSError(domain: "ChatService", code: NSURLErrorTimedOut,
                           userInfo: [NSLocalizedDescriptionKey: "The server took too long to respond. Please try again."])
        }
        return error
    }
}
