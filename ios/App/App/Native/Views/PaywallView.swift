import SwiftUI
import StoreKit

/// Native Pro paywall. Presented from the Settings tab or automatically when the
/// backend returns 429 (free quota exhausted) — `ChatViewModel.limitReached`.
///
/// Reskinned to the Twilight Sanctum look: true-black page, a Marcellus title,
/// plan cards as dark surface panels with gold hairlines (the "best value" plan
/// glows brighter), an uppercase-mono "best value" tag, and gold benefit checks.
/// `Theme` tokens throughout.
@available(iOS 15.0, *)
struct PaywallView: View {
    @ObservedObject var store: NativeStore
    @ObservedObject var auth: AuthManager
    @Environment(\.dismiss) private var dismiss

    private var isSignedIn: Bool {
        if case .authenticated = auth.state { return true }
        return false
    }

    var body: some View {
        ZStack {
            Color.tsBlack.ignoresSafeArea()
            ScrollView {
                VStack(spacing: 24) {
                    header
                    if !isSignedIn {
                        signInGate
                    } else if store.products.isEmpty {
                        ProgressView().tint(.gold).padding(.top, 40)
                    } else {
                        ForEach(store.products, id: \.id) { product in
                            planCard(product)
                        }
                    }
                    benefits
                    if isSignedIn { restoreAndLegal }
                }
                .padding(24)
            }
        }
        .task {
            store.start()
            if store.products.isEmpty { await store.loadProducts() }
        }
        .onChange(of: store.isPro) { pro in
            if pro { dismiss() }   // purchased/restored → close the wall
        }
        .alert("Subscription", isPresented: .constant(store.purchaseError != nil)) {
            Button("OK") { store.purchaseError = nil }
        } message: {
            Text(store.purchaseError ?? "")
        }
    }

    private var header: some View {
        VStack(spacing: 10) {
            Text("PuranGPT Pro")
                .font(.marcellus(34))
                .foregroundColor(.goldBright)
                // Focal-title glow, routed through the capped tier (≤0.30 alpha).
                .goldGlow(.md)
            Text("Unlimited conversations with the sacred texts")
                .font(.inter(15))
                .foregroundColor(.slate)
                .multilineTextAlignment(.center)
        }
        .padding(.top, 12)
    }

    private func planCard(_ product: Product) -> some View {
        let isBest = product.id == "yearly"
        return Button {
            Task { await store.purchase(product) }
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 6) {
                    Text(product.displayName)
                        .font(.marcellus(19))
                        .foregroundColor(.ivory)
                    if isBest {
                        Text("Best value")
                            .uppercaseMonoLabel(size: 9, color: .tsBlack, tracking: 0.14)
                            .padding(.horizontal, 8).padding(.vertical, 3)
                            .background(LinearGradient.goldButton)
                            .clipShape(Capsule())
                    }
                }
                Spacer()
                Text(product.displayPrice)
                    .font(.inter(20, weight: .semibold))
                    .foregroundColor(.goldBright)
            }
            .padding(18)
            .background(Color.surfaceIndigo)
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .strokeBorder(Color.gold.opacity(isBest ? 0.55 : 0.2), lineWidth: 1.5)
            )
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .shadow(color: Color.gold.opacity(isBest ? 0.30 : 0), radius: 14, y: 2)
        }
        .buttonStyle(.plain)
        .disabled(store.isWorking)
    }

    /// Shown to guests: Pro must attach to an account (backend require_auth), so
    /// we gate the plan cards behind sign-in rather than letting them buy a
    /// subscription that can't be granted.
    @State private var showSignIn = false

    private var signInGate: some View {
        VStack(spacing: 14) {
            Text("Sign in to subscribe")
                .font(.marcellus(20))
                .foregroundColor(.ivory)
            Text("Pro unlocks on your account, so your subscription follows you across devices.")
                .font(.inter(15))
                .foregroundColor(.slate)
                .multilineTextAlignment(.center)
            Button {
                showSignIn = true
            } label: {
                Text("Sign In")
                    .font(.inter(16, weight: .semibold))
                    .foregroundColor(.tsBlack)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(Color.gold)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
            }
        }
        .padding(18)
        .background(Color.surface2)
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(Color.goldDeep.opacity(0.22), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .sheet(isPresented: $showSignIn) { SignInView(auth: auth) }
    }

    private var benefits: some View {
        VStack(alignment: .leading, spacing: 12) {
            benefit("Unlimited questions, no daily cap")
            benefit("Deep Research mode across all 23 texts")
            benefit("Exact verse citations, every answer")
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.top, 4)
    }

    private func benefit(_ t: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "checkmark.seal.fill").foregroundColor(.gold)
            Text(t)
                .font(.inter(15))
                .foregroundColor(.ivoryBright.opacity(0.9))
        }
    }

    private var restoreAndLegal: some View {
        VStack(spacing: 12) {
            Button("Restore Purchases") { Task { await store.restore() } }
                .font(.inter(14))
                .foregroundColor(.slate)
                .disabled(store.isWorking)
            Text("Subscriptions renew automatically until cancelled. Manage in Settings › Apple ID.")
                .font(.inter(12))
                .foregroundColor(.slate.opacity(0.7))
                .multilineTextAlignment(.center)
        }
        .padding(.top, 8)
    }
}
