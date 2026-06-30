import SwiftUI
import AuthenticationServices

/// The sign-in sheet. **Sign in with Apple is the prominent default** (Apple's
/// official `SignInWithAppleButton`), with Google / email (the existing Logto
/// flow) offered beneath as a secondary option — satisfying App Store guideline
/// 4.8 (a privacy-preserving login alongside the third-party ones). Twilight
/// Sanctum styling over the true-black void.
struct SignInView: View {
    @ObservedObject var auth: AuthManager
    @Environment(\.dismiss) private var dismiss
    @State private var working = false

    var body: some View {
        ZStack {
            // Web SignInModal is a bordered indigo CARD, not the page void.
            Color.cardIndigo.ignoresSafeArea()

            VStack(spacing: 20) {
                Spacer(minLength: 12)

                // Ceremonial entry — the living orb as a modal accent (web Logo 64).
                BinduOrbView(level: 0.4)
                    .frame(width: 64, height: 64)
                    .allowsHitTesting(false)

                // Gold-gradient title (web text-gradient) — NO headline glow; the
                // restraint law reserves glow for the logo / primary CTA only.
                Text("Enter the Sanctum")
                    .font(.marcellus(28))
                    .foregroundStyle(Color.goldBright)
                    .overlay(
                        LinearGradient(
                            colors: [Color.goldBright, Color.gold],
                            startPoint: .topLeading, endPoint: .bottomTrailing
                        )
                        .mask(Text("Enter the Sanctum").font(.marcellus(28)))
                    )

                Text("Sign in to keep your conversations and unlock more of the path.")
                    .font(.inter(14))
                    .foregroundStyle(Color.dimLabel)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 38)

                Spacer(minLength: 10)

                // PRIMARY — Apple's official Sign in with Apple button. White
                // style for high contrast on the dark void (Apple HIG).
                SignInWithAppleButton(.signIn) { request in
                    auth.prepareAppleRequest(request)
                } onCompletion: { result in
                    working = true
                    Task {
                        await auth.handleAppleCompletion(result)
                        working = false
                        if case .authenticated = auth.state { dismiss() }
                    }
                }
                .signInWithAppleButtonStyle(.white)
                .frame(height: 52)
                .clipShape(RoundedRectangle(cornerRadius: 14))
                .padding(.horizontal, 30)

                // SECONDARY — Google / email via the existing Logto hosted flow.
                Button {
                    working = true
                    Task {
                        await auth.signIn()
                        working = false
                        if case .authenticated = auth.state { dismiss() }
                    }
                } label: {
                    Text("Continue with Google or Email")
                        .font(.inter(15, weight: .medium))
                        .foregroundStyle(Color.ivory.opacity(0.9))
                        .frame(maxWidth: .infinity)
                        .frame(height: 50)
                        .background(
                            // Neutral gray for contrast on the indigo card sheet
                            // (web secondary button #2a2a2a). One Logto hosted flow
                            // serves BOTH Google + email, so it stays one button.
                            RoundedRectangle(cornerRadius: 14)
                                .fill(Color(hex: "#26242e"))
                        )
                        .overlay(
                            RoundedRectangle(cornerRadius: 14)
                                .strokeBorder(Color.borderSoft, lineWidth: 1)
                        )
                }
                .padding(.horizontal, 30)

                Button("Maybe later") { dismiss() }
                    .font(.inter(13))
                    .foregroundStyle(Color.slate)
                    .padding(.top, 2)

                Spacer(minLength: 18)
            }
            .opacity(working ? 0.5 : 1)
            .allowsHitTesting(!working)

            if working {
                ProgressView().tint(Color.gold).scaleEffect(1.2)
            }
        }
    }
}
