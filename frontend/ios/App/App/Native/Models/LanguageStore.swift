import Foundation
import Combine

/// The reply-language preference, the native twin of the web `LanguageSelector`
/// (en / hi / ru). Persisted in `UserDefaults` under `purangpt.language` and
/// shared as a single source of truth: `SettingsView` binds its picker to
/// `code`, and `ChatViewModel` reads `code` when building each `ChatService`
/// request so changing the toggle changes the language of subsequent answers.
///
/// A singleton (rather than a `Deps`-injected value) keeps the Settings picker
/// and the chat reducer reading the exact same instance without re-threading
/// the dependency graph; the default is `"en"`.
@MainActor
final class LanguageStore: ObservableObject {
    static let shared = LanguageStore()

    /// The supported reply languages, matching the backend directive map in
    /// `ChatService` (`langNames` en/hi/ru) and the web selector.
    enum Language: String, CaseIterable, Identifiable {
        case en, hi, ru
        var id: String { rawValue }

        /// Native-script label shown in the picker.
        var label: String {
            switch self {
            case .en: return "English"
            case .hi: return "हिन्दी"
            case .ru: return "Русский"
            }
        }
    }

    private static let key = "purangpt.language"

    /// The persisted language code (`"en"` / `"hi"` / `"ru"`). Writing it
    /// persists to `UserDefaults` immediately so the choice survives relaunch.
    @Published var code: String {
        didSet {
            guard code != oldValue else { return }
            UserDefaults.standard.set(code, forKey: Self.key)
        }
    }

    /// Convenience binding for the SwiftUI `Picker`, mapping `code` ⟷ `Language`.
    var selection: Language {
        get { Language(rawValue: code) ?? .en }
        set { code = newValue.rawValue }
    }

    private init() {
        let stored = UserDefaults.standard.string(forKey: Self.key)
        self.code = Language(rawValue: stored ?? "en")?.rawValue ?? "en"
    }
}
