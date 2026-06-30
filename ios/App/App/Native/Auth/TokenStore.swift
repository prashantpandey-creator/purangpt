import Foundation
import Security

/// Persists the OIDC token set in the iOS Keychain. Access + refresh tokens are
/// secrets; UserDefaults would be wrong. Keyed by a fixed account string under
/// the app's bundle service.
struct TokenSet: Codable {
    var accessToken: String
    var refreshToken: String?
    var idToken: String?
    /// Absolute expiry of the access token (seconds since 1970).
    var expiresAt: Double
}

enum TokenStore {
    private static let service = "com.fcpuru95.purangpt.auth"
    private static let account = "logto_token_set"

    static func save(_ set: TokenSet) {
        guard let data = try? JSONEncoder().encode(set) else { return }
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
        var add = query
        add[kSecValueData as String] = data
        add[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        SecItemAdd(add as CFDictionary, nil)
    }

    static func load() -> TokenSet? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data,
              let set = try? JSONDecoder().decode(TokenSet.self, from: data)
        else { return nil }
        return set
    }

    static func clear() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(query as CFDictionary)
    }

    /// Stable per-install device id for guest quota tracking (mirrors the web's
    /// `purangpt_device_id` in localStorage). Not a secret — fine in UserDefaults.
    static func deviceID() -> String {
        let key = "purangpt_device_id"
        if let existing = UserDefaults.standard.string(forKey: key) { return existing }
        let id = UUID().uuidString
        UserDefaults.standard.set(id, forKey: key)
        return id
    }
}
