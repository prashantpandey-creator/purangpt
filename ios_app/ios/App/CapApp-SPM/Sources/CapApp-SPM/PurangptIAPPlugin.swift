import Foundation
import Capacitor

/// Capacitor bridge for native StoreKit 2 in-app purchases.
/// JS calls `registerPlugin("PurangptIAP")` and these methods route here.
@available(iOS 15.0, *)
@objc(PurangptIAPPlugin)
public class PurangptIAPPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "PurangptIAPPlugin"
    public let jsName = "PurangptIAP"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "getOfferings", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "purchasePackage", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "restorePurchases", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "getEntitlements", returnType: CAPPluginReturnPromise),
    ]

    private let manager = StoreKitManager()

    public override func load() {
        Task {
            await manager.startListening { [weak self] in
                self?.notifyListeners("transactionUpdate", data: [:])
            }
        }
    }

    @objc func getOfferings(_ call: CAPPluginCall) {
        Task {
            do {
                let packages = try await manager.loadProducts()
                var monthly: [String: Any]?
                var annual: [String: Any]?
                for pkg in packages {
                    let id = pkg["identifier"] as? String ?? ""
                    if id.contains("monthly") { monthly = pkg }
                    if id.contains("annual") || id.contains("yearly") { annual = pkg }
                }
                var current: [String: Any] = ["all": packages]
                if let m = monthly { current["monthly"] = m }
                if let a = annual { current["annual"] = a }
                call.resolve(["current": current])
            } catch {
                call.reject(error.localizedDescription)
            }
        }
    }

    @objc func purchasePackage(_ call: CAPPluginCall) {
        guard let productId = call.getString("productId") else {
            call.reject("productId is required")
            return
        }
        Task {
            do {
                let jws = try await manager.purchase(productID: productId)
                if let jws = jws {
                    call.resolve(["success": true, "jws": jws])
                } else {
                    call.resolve(["success": false, "cancelled": true])
                }
            } catch {
                call.reject(error.localizedDescription)
            }
        }
    }

    @objc func restorePurchases(_ call: CAPPluginCall) {
        Task {
            do {
                let jws = try await manager.restore()
                if let jws = jws {
                    call.resolve(["success": true, "jws": jws])
                } else {
                    call.resolve(["success": false])
                }
            } catch {
                call.reject(error.localizedDescription)
            }
        }
    }

    @objc func getEntitlements(_ call: CAPPluginCall) {
        Task {
            let isPro = await manager.hasProEntitlement()
            let jws = await manager.currentEntitlementJWS()
            var result: [String: Any] = ["isPro": isPro]
            if let jws = jws { result["jws"] = jws }
            call.resolve(result)
        }
    }
}
