import Foundation
import StoreKit

/// Native StoreKit 2 store for the SwiftUI paywall. This is the app-target twin
/// of the package-internal `StoreKitManager` (which is shaped for the Capacitor
/// JS bridge). Same product IDs, same JWS-to-backend verification path, but
/// returns typed `Product`s for native UI and POSTs the JWS to the backend's
/// `/api/iap/apple/verify` itself.
///
/// Product IDs are `monthly` / `yearly` in subscription group "PuranGPT Pro"
/// (id 22170114) — confirmed in ios-payments-storekit memory. Apple pricing is
/// independent of the web Stripe price.
@available(iOS 15.0, *)
@MainActor
final class NativeStore: ObservableObject {
    static let productIDs = ["monthly", "yearly"]
    private static let proIDs = Set(productIDs)

    @Published private(set) var products: [Product] = []
    @Published private(set) var isPro = false
    @Published var purchaseError: String?
    @Published var isWorking = false

    private let baseURL: URL
    private let tokenProvider: () async -> String?
    private var updatesTask: Task<Void, Never>?

    init(baseURL: URL, tokenProvider: @escaping () async -> String?) {
        self.baseURL = baseURL
        self.tokenProvider = tokenProvider
    }

    /// Begin observing transaction updates (renewals, Ask-to-Buy, refunds,
    /// cross-device). Each verified update re-syncs Pro state with the backend.
    func start() {
        guard updatesTask == nil else { return }
        updatesTask = Task { [weak self] in
            for await update in Transaction.updates {
                guard case .verified(let txn) = update else { continue }
                await txn.finish()
                await self?.refreshEntitlement()
            }
        }
    }

    deinit { updatesTask?.cancel() }

    func loadProducts() async {
        do {
            let fetched = try await Product.products(for: Self.productIDs)
            // Stable order: monthly first, then yearly.
            products = fetched.sorted { ($0.id == "monthly" ? 0 : 1) < ($1.id == "monthly" ? 0 : 1) }
        } catch {
            purchaseError = "Couldn't load subscriptions. \(error.localizedDescription)"
        }
    }

    /// Purchase a product, then verify the JWS with the backend to grant Pro.
    func purchase(_ product: Product) async {
        isWorking = true; purchaseError = nil
        defer { isWorking = false }
        do {
            let result = try await product.purchase()
            switch result {
            case .success(let verification):
                guard case .verified(let txn) = verification else {
                    purchaseError = "Purchase couldn't be verified by the App Store."
                    return
                }
                let jws = verification.jwsRepresentation
                await txn.finish()
                await grantViaBackend(jws: jws)
            case .userCancelled, .pending:
                break
            @unknown default:
                break
            }
        } catch {
            purchaseError = "Purchase failed. \(error.localizedDescription)"
        }
    }

    /// Restore: force an App Store sync and re-verify any active entitlement.
    func restore() async {
        isWorking = true; purchaseError = nil
        defer { isWorking = false }
        try? await AppStore.sync()
        await refreshEntitlement()
        if !isPro { purchaseError = "No active subscription found to restore." }
    }

    /// Re-derive Pro state from the current entitlement and confirm with backend.
    func refreshEntitlement() async {
        for await result in Transaction.currentEntitlements {
            guard case .verified(let txn) = result else { continue }
            guard Self.proIDs.contains(txn.productID) else { continue }
            if txn.revocationDate != nil { continue }
            if let exp = txn.expirationDate, exp < Date() { continue }
            await grantViaBackend(jws: result.jwsRepresentation)
            return
        }
        isPro = false
    }

    /// POST the JWS to /api/iap/apple/verify (Bearer-authed). Backend verifies
    /// Apple's signature locally and activates the subscription.
    private func grantViaBackend(jws: String) async {
        guard let token = await tokenProvider() else {
            // require_auth on the backend — must be signed in to grant Pro.
            purchaseError = "Sign in first to activate Pro on your account."
            return
        }
        var req = URLRequest(url: baseURL.appendingPathComponent("/api/iap/apple/verify"))
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        req.httpBody = try? JSONSerialization.data(withJSONObject: ["jws": jws])

        guard
            let (data, resp) = try? await URLSession.shared.data(for: req),
            let http = resp as? HTTPURLResponse, (200...299).contains(http.statusCode),
            let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any]
        else {
            purchaseError = "Couldn't reach the server to activate Pro. Try Restore."
            return
        }
        isPro = (json["is_pro"] as? Bool) ?? false
        if !isPro && (json["verified"] as? Bool) == false {
            purchaseError = "The App Store transaction wasn't recognized."
        }
    }
}
