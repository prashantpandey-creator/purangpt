import SwiftUI

/// Native root scene. Hosts the chat and an auth affordance. Builds the
/// `ChatService` with the live `AuthManager.tokenProvider`, so a signed-in user
/// streams as themselves and a guest streams under the device-id quota.
struct RootView: View {
    @StateObject private var auth = AuthManager()
    @State private var deps: Deps?

    /// Everything that depends on the authenticated token provider, built once
    /// in `.task` and held as a unit so the TabView only renders when ready.
    @MainActor
    final class Deps: ObservableObject {
        let chat: ChatService
        let library: LibraryService
        /// The single canonical chat VM. Drives `ChatView` (the Ask tab), owns the
        /// transcript + streaming reducer, the 429 paywall trigger, history replay
        /// (`load(history:)`), and the `orbLevel` that drives the Metal Bindu orb
        /// backdrop.
        let chatVM: ChatViewModel
        let store: NativeStore
        let baseURL: URL

        init(baseURL: URL, auth: AuthManager) {
            self.baseURL = baseURL
            let device = TokenStore.deviceID()
            let provider = auth.tokenProvider()
            self.chat = ChatService(baseURL: baseURL, deviceID: device, tokenProvider: provider)
            self.library = LibraryService(baseURL: baseURL, deviceID: device, tokenProvider: provider)
            self.chatVM = ChatViewModel(service: chat)
            self.store = NativeStore(baseURL: baseURL, tokenProvider: provider)
        }
    }

    /// Base URL of the FastAPI backend. Overridable via Info.plist key
    /// `BackendBaseURL` for local dev; defaults to production.
    private var backendBaseURL: URL {
        if let s = Bundle.main.object(forInfoDictionaryKey: "BackendBaseURL") as? String,
           let u = URL(string: s) { return u }
        return URL(string: "https://purangpt.com")!
    }

    var body: some View {
        ZStack {
            // True-black void base (shipped web globals.css :root --bg-deep #000000).
            Color.tsBlack.ignoresSafeArea()

            if let deps {
                TabsView(auth: auth, deps: deps)
            } else {
                ProgressView().tint(Color.gold)
            }
        }
        .task {
            await auth.restore()
            if deps == nil {
                let d = Deps(baseURL: backendBaseURL, auth: auth)
                await d.store.refreshEntitlement()
                deps = d
            }
        }
    }

}

/// The tab container. Observes `chatVM` and `store` directly so the 429 paywall
/// trigger and Pro state changes actually drive re-renders.
private struct TabsView: View {
    @ObservedObject var auth: AuthManager
    let deps: RootView.Deps
    /// The single canonical chat VM drives the Ask tab (Metal Bindu orb backdrop
    /// via `orbLevel`), the paywall trigger, the new-chat button, and history
    /// replay.
    @ObservedObject private var chatVM: ChatViewModel
    @State private var showPaywall = false
    @State private var showHistory = false
    @State private var showSignIn = false

    init(auth: AuthManager, deps: RootView.Deps) {
        self.auth = auth
        self.deps = deps
        self._chatVM = ObservedObject(wrappedValue: deps.chatVM)
        Self.configureTabBarAppearance()
    }

    /// Soften the system tab bar to match the web: a dark translucent material
    /// over the true-black void, a thin gold hairline along the top edge, gold
    /// (#cba455) for the selected item and a dim ivory for the rest. Configured
    /// imperatively because SwiftUI exposes no native hook for the bar material
    /// or its top hairline.
    private static func configureTabBarAppearance() {
        let appearance = UITabBarAppearance()
        // Dark translucent material floating over the void (not a flat fill).
        appearance.configureWithDefaultBackground()
        appearance.backgroundEffect = UIBlurEffect(style: .systemUltraThinMaterialDark)
        // True-black base tint, mostly transparent so the blur reads as material.
        appearance.backgroundColor = UIColor(Color.tsBlack).withAlphaComponent(0.32)
        // Thin gold hairline along the top edge (border-soft, web globals.css).
        appearance.shadowColor = UIColor(Color.borderSoft)

        let gold = UIColor(Color.gold)
        let dim = UIColor(Color.dimLabel)
        for item in [appearance.stackedLayoutAppearance,
                     appearance.inlineLayoutAppearance,
                     appearance.compactInlineLayoutAppearance] {
            item.selected.iconColor = gold
            item.selected.titleTextAttributes = [.foregroundColor: gold]
            item.normal.iconColor = dim
            item.normal.titleTextAttributes = [.foregroundColor: dim]
        }

        UITabBar.appearance().standardAppearance = appearance
        UITabBar.appearance().scrollEdgeAppearance = appearance
    }

    var body: some View {
        TabView {
            VStack(spacing: 0) {
                chatHeader
                // The canonical native chat surface: tappable citations →
                // SourceDetailView (via the injected library), Metal Bindu orb
                // backdrop driven by `chatVM.orbLevel`.
                ChatView(vm: deps.chatVM, library: deps.library)
            }
            // Carry the true-black void up THROUGH the status bar / top safe
            // area. Without this the TabView paints its default (white) system
            // background behind the transparent header, leaving a white strip
            // under the clock — the web is true-black edge to edge.
            .background(Color.tsBlack.ignoresSafeArea())
            .tabItem { Label("Ask", systemImage: "sparkles") }

            LibraryView(service: deps.library)
                .tabItem { Label("Library", systemImage: "books.vertical.fill") }

            MoreView(baseURL: deps.baseURL)
                .tabItem { Label("More", systemImage: "ellipsis.circle") }

            SettingsView(auth: auth, store: deps.store)
                .tabItem { Label("Settings", systemImage: "gearshape.fill") }
        }
        .tint(Color.gold)
        .onChange(of: chatVM.limitReached) { reached in
            if reached { showPaywall = true }
        }
        .sheet(isPresented: $showPaywall, onDismiss: { chatVM.limitReached = false }) {
            PaywallView(store: deps.store, auth: auth)
        }
        .sheet(isPresented: $showHistory) {
            // Selecting a past session replays its full transcript into the chat
            // (ChatViewModel.load(history:) rehydrates messages + session id).
            HistoryView(service: deps.library) { history in
                chatVM.load(history: history)
            }
        }
        .sheet(isPresented: $showSignIn) {
            // Apple-default sign-in (Apple's system sheet) + Google/email (Logto).
            SignInView(auth: auth)
        }
    }

    /// Chat-tab header: wordmark + new-chat + history + auth. Lives here (not in
    /// RootView) so the buttons can reach the VM and library service.
    ///
    /// Transparent — it floats over the void rather than sitting on a solid bar,
    /// matching the web `DashboardShell` top strip. The buttons are the web's
    /// 36pt ghost-gold circular affordances (bg gold@0.07, 1px gold@0.25 border,
    /// gold icon, faint gold halo). iOS top safe-area padding is preserved so it
    /// clears the status bar / notch.
    private var chatHeader: some View {
        HStack(spacing: 10) {
            Image("LogoEmblem")
                .resizable()
                .scaledToFit()
                .frame(width: 30, height: 30)
                // Gold reads as natural flame — a soft, capped focal glow.
                .goldGlow(.sm)
            Text("PuranGPT")
                .font(.marcellus(20))
                .foregroundStyle(Color.goldBright)
            Spacer()
            ghostCircleButton(icon: "square.and.pencil",
                              accessibility: "New conversation") {
                chatVM.newConversation()
            }
            ghostCircleButton(icon: "clock.arrow.circlepath",
                              accessibility: "History") {
                showHistory = true
            }
            authButton
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .padding(.bottom, 10)
        // Transparent: the header floats over the true-black void / Bindu orb.
        .background(Color.clear)
    }

    /// The web's 36pt ghost-gold circular button (DashboardShell): a faint gold
    /// wash, a hairline gold ring, a gold glyph, and a soft gold halo.
    private func ghostCircleButton(
        icon: String,
        accessibility: String,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            Image(systemName: icon)
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(Color.gold)
                .frame(width: 36, height: 36)
                .background(Color.gold.opacity(0.07))
                .clipShape(Circle())
                .overlay(Circle().stroke(Color.gold.opacity(0.25), lineWidth: 1))
                .goldGlow(.restingButton)
        }
        .accessibilityLabel(accessibility)
    }

    @ViewBuilder
    private var authButton: some View {
        switch auth.state {
        case .authenticated(let email):
            Menu {
                if let email { Text(email) }
                Button("Sign Out", role: .destructive) { auth.signOut() }
            } label: {
                Image(systemName: "person.crop.circle.fill")
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(Color.gold)
                    .frame(width: 36, height: 36)
                    .background(Color.gold.opacity(0.07))
                    .clipShape(Circle())
                    .overlay(Circle().stroke(Color.gold.opacity(0.25), lineWidth: 1))
                    .goldGlow(.restingButton)
            }
            .accessibilityLabel("Account")
        case .guest, .unknown:
            Button("Sign In") { showSignIn = true }
                .font(.inter(14, weight: .semibold))
                .foregroundStyle(Color.tsBlack)
                .padding(.horizontal, 14).padding(.vertical, 8)
                .background(LinearGradient.goldButton)
                .clipShape(Capsule())
        }
    }
}
