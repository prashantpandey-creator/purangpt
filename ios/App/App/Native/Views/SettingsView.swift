import SwiftUI

/// Settings tab: account state, Pro status / upgrade entry, restore, sign out.
///
/// Reskinned to the shipped-web "Twilight Sanctum" look: a true-black page, the
/// generic UIKit insetGrouped `List` replaced by custom dark cards (rounded ~16,
/// gold-deep hairline, surface bg), Marcellus screen/section titles, and the
/// uppercase-mono label style for the section headers. Uses the `Theme` tokens
/// (Color statics + Font helpers) throughout — no raw hex, no system grouped list.
@available(iOS 15.0, *)
struct SettingsView: View {
    @ObservedObject var auth: AuthManager
    @ObservedObject var store: NativeStore
    @ObservedObject private var language = LanguageStore.shared
    @State private var showPaywall = false

    var body: some View {
        NavigationView {
            ZStack {
                Color.tsBlack.ignoresSafeArea()
                ScrollView {
                    VStack(spacing: 22) {
                        screenTitle
                        accountCard
                        languageCard
                        proCard
                        aboutCard
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
                    .padding(.bottom, 32)
                }
            }
            .navigationBarHidden(true)
        }
        .navigationViewStyle(.stack)
        .sheet(isPresented: $showPaywall) {
            PaywallView(store: store, auth: auth)
        }
        .task { await store.refreshEntitlement() }
    }

    // ── Screen title (Marcellus, the web wordmark register) ─────────────────
    private var screenTitle: some View {
        HStack {
            Text("Settings")
                .font(.marcellus(30))
                .foregroundColor(.goldBright)
            Spacer()
        }
        .padding(.top, 6)
    }

    // ── Account ─────────────────────────────────────────────────────────────
    @State private var showSignIn = false

    private var accountCard: some View {
        SanctumCard(header: "Account") {
            switch auth.state {
            case .authenticated(let email):
                row("Signed in", email ?? "Account")
                Divider().overlay(Color.borderSoft)
                Button { auth.signOut() } label: {
                    HStack {
                        Text("Sign Out")
                            .font(.inter(15, weight: .medium))
                            .foregroundColor(.dimLabel)
                        Spacer()
                    }
                }
                .buttonStyle(.plain)
            case .guest, .unknown:
                Button { showSignIn = true } label: {
                    HStack {
                        Text("Sign In")
                            .font(.inter(15, weight: .semibold))
                            .foregroundColor(.gold)
                        Spacer()
                        Image(systemName: "arrow.right")
                            .font(.system(size: 12))
                            .foregroundColor(.gold)
                    }
                }
                .buttonStyle(.plain)
            }
        }
        .sheet(isPresented: $showSignIn) { SignInView(auth: auth) }
    }

    // ── Language ────────────────────────────────────────────────────────────
    /// Reply-language picker, the native twin of the web `LanguageSelector`.
    /// Bound to the shared `LanguageStore`, whose `code` `ChatViewModel` reads
    /// when building each request — so the choice steers subsequent answers.
    private var languageCard: some View {
        SanctumCard(header: "Language") {
            HStack {
                Text("Reply Language")
                    .font(.inter(15))
                    .foregroundColor(.ivory)
                Spacer()
            }
            // Gold pill toggles (the web LanguageSelector look) — NOT the iOS
            // segmented control, which was a generic-iOS tell.
            HStack(spacing: 8) {
                ForEach(LanguageStore.Language.allCases) { lang in
                    Button {
                        language.selection = lang
                    } label: {
                        Text(lang.label)
                            .font(.inter(13, weight: language.selection == lang ? .semibold : .medium))
                            .foregroundColor(language.selection == lang ? .goldBright : .slate)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 9)
                            .background(
                                Capsule().fill(Color.gold.opacity(language.selection == lang ? 0.16 : 0.05))
                            )
                            .overlay(
                                Capsule().strokeBorder(
                                    Color.gold.opacity(language.selection == lang ? 0.40 : 0.14),
                                    lineWidth: 1
                                )
                            )
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.top, 4)
        }
    }

    // ── Subscription ────────────────────────────────────────────────────────
    private var proCard: some View {
        SanctumCard(header: "Subscription") {
            if store.isPro {
                HStack(spacing: 10) {
                    Image(systemName: "checkmark.seal.fill")
                        .foregroundColor(.gold)
                    Text("PuranGPT Pro active")
                        .font(.inter(15, weight: .medium))
                        .foregroundColor(.ivory)
                    Spacer()
                }
            } else {
                Button { showPaywall = true } label: {
                    HStack(spacing: 10) {
                        Image(systemName: "sparkles").foregroundColor(.goldBright)
                        Text("Upgrade to Pro")
                            .font(.inter(15, weight: .semibold))
                            .foregroundColor(.goldBright)
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.system(size: 12)).foregroundColor(.goldDeep)
                    }
                }
                .buttonStyle(.plain)
                Divider().overlay(Color.borderSoft)
                Button { Task { await store.restore() } } label: {
                    HStack {
                        Text("Restore Purchases")
                            .font(.inter(14))
                            .foregroundColor(.slate)
                        Spacer()
                    }
                }
                .buttonStyle(.plain)
            }
        }
    }

    // ── About ───────────────────────────────────────────────────────────────
    private var aboutCard: some View {
        SanctumCard(header: "About") {
            row("Version", appVersion)
            Divider().overlay(Color.borderSoft)
            linkRow("Privacy Policy", "https://purangpt.com/privacy")
            Divider().overlay(Color.borderSoft)
            linkRow("Terms", "https://purangpt.com/terms")
        }
    }

    private func linkRow(_ label: String, _ url: String) -> some View {
        Link(destination: URL(string: url)!) {
            HStack {
                Text(label)
                    .font(.inter(15))
                    .foregroundColor(.slate)
                Spacer()
                Image(systemName: "arrow.up.right")
                    .font(.system(size: 11))
                    .foregroundColor(.slate.opacity(0.7))
            }
        }
    }

    /// iOS 15-safe key/value row (LabeledContent is iOS 16+).
    private func row(_ label: String, _ value: String) -> some View {
        HStack {
            Text(label)
                .font(.inter(15))
                .foregroundColor(.ivory)
            Spacer()
            Text(value)
                .font(.inter(14))
                .foregroundColor(.slate)
        }
    }

    private var appVersion: String {
        let v = Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "1.0"
        let b = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "?"
        return "\(v) (\(b))"
    }
}

// MARK: - Shared dark card (replaces the system insetGrouped List look)

/// A single Twilight-Sanctum card: a surface-toned rounded panel on the true
/// black page, framed by a gold-deep hairline, with an uppercase-mono section
/// header floating just above it. This is the native answer to the web's
/// `rounded-xl` panels with `1px solid rgba(203,164,85,…)` borders — it is what
/// removes the "generic iOS grouped List" tell. Defined here (not `private`) so
/// the other reskinned secondary screens reuse the exact same chrome.
@available(iOS 15.0, *)
struct SanctumCard<Content: View>: View {
    let header: String?
    @ViewBuilder var content: () -> Content

    init(header: String? = nil, @ViewBuilder content: @escaping () -> Content) {
        self.header = header
        self.content = content
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if let header {
                Text(header)
                    .uppercaseMonoLabel(size: 11, color: .goldDeep, tracking: 0.18)
                    .padding(.leading, 4)
            }
            VStack(alignment: .leading, spacing: 14) {
                content()
            }
            .padding(16)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.cardIndigo)
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .strokeBorder(Color.goldDeep.opacity(0.22), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 16))
        }
    }
}
