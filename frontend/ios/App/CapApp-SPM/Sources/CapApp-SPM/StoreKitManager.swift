import Foundation
import StoreKit

/// Pure StoreKit 2 logic — no Capacitor imports.
/// Owns product loading, purchase, restore, and the long-lived transaction
/// listener. Everything returns plain dictionaries / values that the Capacitor
/// bridge layer (PurangptIAPPlugin) can hand straight to JS.
@available(iOS 15.0, *)
actor StoreKitManager {

    static let productIDs: [String] = ["monthly", "yearly"]
    static let proProductIDs: Set<String> = Set(productIDs)

    private var products: [Product] = []
    private var updatesTask: Task<Void, Never>?

    /// Called by the plugin to begin observing transaction updates (renewals,
    /// Ask-to-Buy approvals, cross-device purchases, refunds). The handler is
    /// invoked on every verified update so the bridge can re-sync the web layer.
    func startListening(onUpdate: @escaping @Sendable () -> Void) {
        guard updatesTask == nil else { return }
        updatesTask = Task.detached {
            for await update in Transaction.updates {
                if case .verified(let transaction) = update {
                    await transaction.finish()
                    onUpdate()
                }
            }
        }
    }

    // MARK: - Products

    func loadProducts() async throws -> [[String: Any]] {
        let fetched = try await Product.products(for: StoreKitManager.productIDs)
        self.products = fetched
        return fetched.map { Self.serialize($0) }
    }

    private func product(for id: String) -> Product? {
        products.first { $0.id == id }
    }

    // MARK: - Purchase

    /// Returns the signed JWS for the new transaction on success, or nil if the
    /// user cancelled / the purchase is pending.
    func purchase(productID: String) async throws -> String? {
        var target = product(for: productID)
        if target == nil {
            _ = try await loadProducts()
            target = product(for: productID)
        }
        guard let product = target else {
            throw IAPError.productNotFound(productID)
        }

        let result = try await product.purchase()
        switch result {
        case .success(let verification):
            let transaction = try Self.checkVerified(verification)
            let jws = verification.jwsRepresentation
            await transaction.finish()
            return jws
        case .userCancelled:
            return nil
        case .pending:
            return nil
        @unknown default:
            return nil
        }
    }

    // MARK: - Restore

    /// Forces an App Store sync, then returns the JWS of any active Pro
    /// entitlement (or nil if none).
    func restore() async throws -> String? {
        try? await AppStore.sync()
        return await currentEntitlementJWS()
    }

    // MARK: - Entitlements

    /// True if the user currently holds an active Pro entitlement.
    func hasProEntitlement() async -> Bool {
        await currentEntitlementJWS() != nil
    }

    /// The signed JWS of the current active Pro entitlement, for backend
    /// verification. Returns nil if no active Pro subscription exists.
    func currentEntitlementJWS() async -> String? {
        for await result in Transaction.currentEntitlements {
            guard case .verified(let transaction) = result else { continue }
            guard StoreKitManager.proProductIDs.contains(transaction.productID) else { continue }
            if transaction.revocationDate != nil { continue }
            if let exp = transaction.expirationDate, exp < Date() { continue }
            return result.jwsRepresentation
        }
        return nil
    }

    // MARK: - Helpers

    private static func checkVerified<T>(_ result: VerificationResult<T>) throws -> T {
        switch result {
        case .verified(let safe):
            return safe
        case .unverified:
            throw IAPError.failedVerification
        }
    }

    private static func serialize(_ product: Product) -> [String: Any] {
        // Shape matches the JS `Pkg` contract: { identifier, product: { ... } }
        return [
            "identifier": product.id,
            "product": [
                "identifier": product.id,
                "priceString": product.displayPrice,
                "price": (product.price as NSDecimalNumber).doubleValue,
                "currencyCode": product.priceFormatStyle.currencyCode ?? "USD",
                "title": product.displayName,
                "description": product.description,
            ] as [String: Any],
        ]
    }

    enum IAPError: LocalizedError {
        case productNotFound(String)
        case failedVerification

        var errorDescription: String? {
            switch self {
            case .productNotFound(let id): return "Product not found: \(id)"
            case .failedVerification: return "Transaction failed App Store verification"
            }
        }
    }
}
