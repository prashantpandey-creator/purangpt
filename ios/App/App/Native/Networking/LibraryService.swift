import Foundation

/// Read-only client for the catalog / explorer / text endpoints. Same direct-to-
/// FastAPI contract as `ChatService` (Bearer + X-Device-ID). All GETs; decoding
/// uses the models' own CodingKeys (no global keyDecodingStrategy, because some
/// keys like `text_id` are mapped explicitly and others are already camelCase).
actor LibraryService {
    private let baseURL: URL
    private let deviceID: String
    private let tokenProvider: () async -> String?

    init(baseURL: URL, deviceID: String, tokenProvider: @escaping () async -> String?) {
        self.baseURL = baseURL
        self.deviceID = deviceID
        self.tokenProvider = tokenProvider
    }

    /// GET /api/puranas → the text catalog.
    func catalog() async throws -> [PuranaRef] {
        struct Envelope: Codable { let puranas: [PuranaRef] }
        let env: Envelope = try await get("/api/puranas")
        return env.puranas
    }

    /// GET /api/explore/{id}/intro → the AI guide intro (slow: LLM-generated,
    /// cached server-side after first call).
    func intro(for textID: String) async throws -> ExploreIntro {
        try await get("/api/explore/\(textID)/intro", timeout: 60)
    }

    /// GET /api/text/{id}?page&size → a page of raw lines.
    func textPage(_ textID: String, page: Int = 1, size: Int = 100) async throws -> TextPage {
        try await get("/api/text/\(textID)?page=\(page)&size=\(size)")
    }

    /// GET /api/verses/{chunk_id}/similar → semantically related verses.
    func similarVerses(_ chunkID: String, topK: Int = 6) async throws -> [SimilarVerse] {
        struct Envelope: Codable { let similar: [SimilarVerse] }
        let env: Envelope = try await get("/api/verses/\(chunkID)/similar?top_k=\(topK)")
        return env.similar
    }

    // MARK: - Chat sessions

    /// GET /api/sessions → past conversations (keyed by user or X-Device-ID).
    func sessions() async throws -> [SessionSummary] {
        struct Envelope: Codable { let sessions: [SessionSummary] }
        let env: Envelope = try await get("/api/sessions")
        return env.sessions
    }

    /// GET /api/session/{id} → a session's recent message history.
    func sessionHistory(_ id: String) async throws -> SessionHistory {
        try await get("/api/session/\(id)")
    }

    /// DELETE /api/session/{id} → clear a conversation.
    func deleteSession(_ id: String) async throws {
        try await send("DELETE", "/api/session/\(id)")
    }

    // MARK: - Plumbing

    private func get<T: Decodable>(_ path: String, timeout: TimeInterval = 20) async throws -> T {
        guard let url = URL(string: path, relativeTo: baseURL) else {
            throw URLError(.badURL)
        }
        var req = URLRequest(url: url)
        req.timeoutInterval = timeout
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        req.setValue(deviceID, forHTTPHeaderField: "X-Device-ID")
        if let token = await tokenProvider() {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let (data, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse else { throw URLError(.badServerResponse) }
        guard (200...299).contains(http.statusCode) else {
            throw NSError(domain: "LibraryService", code: http.statusCode,
                          userInfo: [NSLocalizedDescriptionKey: "Request failed (\(http.statusCode)) for \(path)."])
        }
        return try JSONDecoder().decode(T.self, from: data)
    }

    /// A method call (e.g. DELETE) where the response body is ignored.
    private func send(_ method: String, _ path: String, timeout: TimeInterval = 20) async throws {
        guard let url = URL(string: path, relativeTo: baseURL) else { throw URLError(.badURL) }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.timeoutInterval = timeout
        req.setValue(deviceID, forHTTPHeaderField: "X-Device-ID")
        if let token = await tokenProvider() {
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let (_, resp) = try await URLSession.shared.data(for: req)
        guard let http = resp as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            let code = (resp as? HTTPURLResponse)?.statusCode ?? -1
            throw NSError(domain: "LibraryService", code: code,
                          userInfo: [NSLocalizedDescriptionKey: "\(method) failed (\(code)) for \(path)."])
        }
    }
}
