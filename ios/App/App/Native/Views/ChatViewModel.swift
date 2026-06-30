import Foundation
import SwiftUI

/// Drives `ChatView`: holds the transcript, consumes the `ChatService` stream,
/// and reduces typed `ChatEvent`s into UI state. Mirrors the reducer logic the
/// web `useChat` hook performs over `streamChat`.
@MainActor
final class ChatViewModel: ObservableObject {
    @Published var messages: [ChatMessageVM] = []
    @Published var draft: String = ""
    @Published var isStreaming = false
    /// Set when the backend returns 429 — the host view observes this to
    /// present the native paywall (Phase 3).
    @Published var limitReached = false
    /// When on, the next message uses the backend's `deep` mode (the
    /// DeepResearchAgent at main.py `if request.mode == "deep"`). Quota-gated —
    /// a guest/over-limit user 429s, which routes to the paywall like normal chat.
    @Published var deepResearch = false
    /// A transient status line surfaced during streaming (e.g. "🔍 Searching…").
    @Published var statusLine: String?
    /// Eased 0…1 ENERGY level fed to the Metal "Eye of the Void" orb backdrop.
    /// The Eye is already a single form, so `lv` drives its ACTIVITY, not any
    /// convergence: idle/settle = LOW (0.25, a calm eye with gentle shockwaves),
    /// user-send / thinking = 0.85 (the eye stirs), streaming / sources landed =
    /// 1.0 (the eye flares), then it eases back to 0.25 after the answer.
    /// `BinduMetalView` applies its own per-frame easing toward this target, so
    /// the animation here is the coarse step.
    @Published var orbLevel: Double = 0.25

    private let service: ChatService
    private var streamTask: Task<Void, Never>?
    /// The current conversation's server-side session id. A fresh UUID per new
    /// conversation so history lists distinct threads (the backend persists by
    /// this id, keyed to the user/device). The first session keeps "default" so
    /// existing behaviour is unchanged until the user starts a new chat.
    private(set) var sessionID = "default"

    init(service: ChatService) {
        self.service = service
    }

    func send() async {
        if isStreaming { stop(); return }

        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        draft = ""

        messages.append(.user(text))
        var assistant = ChatMessageVM.assistantPending()
        messages.append(assistant)
        let assistantID = assistant.id
        isStreaming = true

        statusLine = nil
        setOrb(0.85) // user sent — the eye stirs (thinking, no tokens yet)
        // Reply language comes from the shared, UserDefaults-backed store the
        // Settings picker writes to — so changing the toggle changes the
        // language of subsequent answers (default "en").
        let req = ChatService.Request(query: text,
                                      mode: deepResearch ? .deep : .chat,
                                      sessionID: sessionID,
                                      language: LanguageStore.shared.code)

        streamTask = Task {
            do {
                for try await event in await service.stream(req) {
                    apply(event, to: assistantID, accumulator: &assistant)
                }
            } catch is CancellationError {
                // user pressed stop — leave partial content as-is
            } catch let limit as LimitReachedError {
                update(assistantID) {
                    $0.pending = false
                    $0.error = true
                    $0.content = limit.message
                }
                limitReached = true
            } catch {
                update(assistantID) {
                    $0.pending = false
                    $0.error = true
                    $0.content = error.localizedDescription
                }
            }
            isStreaming = false
            statusLine = nil
            setOrb(0.25) // answer done — the eye eases back to a calm idle
        }
    }

    func stop() {
        streamTask?.cancel()
        streamTask = nil
        isStreaming = false
        statusLine = nil
        setOrb(0.25) // user stopped — the eye eases back to a calm idle
        if let last = messages.last, last.role == .assistant {
            update(last.id) { $0.pending = false }
        }
    }

    /// Start a fresh conversation: clear the transcript and mint a new session id.
    func newConversation() {
        stop()
        messages.removeAll()
        statusLine = nil
        sessionID = UUID().uuidString
    }

    /// Re-run the user question that produced the given assistant answer: drop
    /// that question/answer pair and stream a fresh response for the same query.
    func regenerate(_ assistantID: String) async {
        guard let aIdx = messages.firstIndex(where: { $0.id == assistantID }),
              let uIdx = messages[..<aIdx].lastIndex(where: { $0.role == .user })
        else { return }
        let query = messages[uIdx].content
        if isStreaming { stop() }
        messages.removeSubrange(uIdx...)
        draft = query
        await send()
    }

    /// Rehydrate the transcript from a persisted session's history and switch the
    /// active session id to it, so the next message continues that thread.
    func load(history: SessionHistory) {
        stop()
        sessionID = history.sessionId
        messages = history.history.map { msg in
            ChatMessageVM(
                id: UUID().uuidString,
                role: msg.role == "user" ? .user : .assistant,
                content: msg.content,
                sources: msg.sources ?? [],
                reasoning: nil,
                pending: false,
                error: false
            )
        }
    }

    private func apply(_ event: ChatEvent, to id: String, accumulator: inout ChatMessageVM) {
        switch event {
        case .token(let chunk):
            update(id) { $0.pending = false; $0.content += chunk }
            setOrb(1.0) // the answer is pouring out — the eye flares at full energy
        case .reasoning(let r):
            update(id) { $0.reasoning = ($0.reasoning ?? "") + r }
        case .sources(let s):
            update(id) { $0.sources = s }
            setOrb(1.0) // sources landed — peak energy
        case .status(let msg):
            // Deep research emits a stream of these ("🔍 Searching…", "🤔
            // Analyzing…"); show the latest so the UI doesn't look frozen.
            statusLine = msg
        case .visual:
            break
        case .error(let msg):
            statusLine = nil
            update(id) { $0.pending = false; $0.error = true; $0.content = msg }
        case .done(let sid):
            if let sid { sessionID = sid }
            statusLine = nil
            update(id) { $0.pending = false }
        case .unknown:
            break
        }
    }

    /// Ease the orb's convergence target. `BinduMetalView` does its own per-frame
    /// interpolation toward this value, so the SwiftUI animation just smooths the
    /// `@Published` transition for any observers.
    private func setOrb(_ target: Double) {
        withAnimation(.easeInOut(duration: 0.6)) { orbLevel = max(0, min(1, target)) }
    }

    private func update(_ id: String, _ mutate: (inout ChatMessageVM) -> Void) {
        guard let idx = messages.firstIndex(where: { $0.id == id }) else { return }
        mutate(&messages[idx])
    }
}
