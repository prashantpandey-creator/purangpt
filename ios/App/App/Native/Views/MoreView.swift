import SwiftUI

/// The "More" tab: a directory of the long-tail web routes hosted in-app via
/// WebRouteView. These pages aren't worth a native rewrite, but the native shell
/// keeps users from bouncing to Safari.
///
/// Reskinned to the Twilight Sanctum look: true-black page, the system
/// insetGrouped `List` replaced by custom dark `SanctumCard`s on true black,
/// Marcellus screen title, uppercase-mono section headers, gold-deep hairline
/// rows. No raw hex / no system grouped list.
@available(iOS 15.0, *)
struct MoreView: View {
    let baseURL: URL

    private struct Route: Identifiable {
        let id = UUID()
        let title: String
        let path: String
        let icon: String
    }

    private let explore: [Route] = [
        .init(title: "About", path: "/about", icon: "info.circle"),
        .init(title: "Blog", path: "/blog", icon: "newspaper"),
        .init(title: "Documentation", path: "/docs", icon: "book.closed"),
        .init(title: "FAQ", path: "/faq", icon: "questionmark.circle"),
        .init(title: "Community", path: "/community", icon: "person.3"),
        .init(title: "Contact", path: "/contact", icon: "envelope"),
    ]

    private let legal: [Route] = [
        .init(title: "Privacy Policy", path: "/privacy", icon: "lock.shield"),
        .init(title: "Terms of Service", path: "/terms", icon: "doc.text"),
        .init(title: "Refund Policy", path: "/refund", icon: "arrow.uturn.backward"),
        .init(title: "Transparency", path: "/transparency", icon: "eye"),
        .init(title: "Status", path: "/status", icon: "waveform.path.ecg"),
    ]

    var body: some View {
        NavigationView {
            ZStack {
                Color.tsBlack.ignoresSafeArea()
                ScrollView {
                    VStack(spacing: 22) {
                        HStack {
                            Text("More")
                                .font(.marcellus(30))
                                .foregroundColor(.goldBright)
                            Spacer()
                        }
                        .padding(.top, 6)
                        section("Explore", explore)
                        section("Legal & More", legal)
                    }
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
                    .padding(.bottom, 32)
                }
            }
            .navigationBarHidden(true)
        }
        .navigationViewStyle(.stack)
    }

    private func section(_ title: String, _ routes: [Route]) -> some View {
        SanctumCard(header: title) {
            ForEach(Array(routes.enumerated()), id: \.element.id) { idx, route in
                NavigationLink {
                    WebRouteView(title: route.title,
                                 url: URL(string: route.path, relativeTo: baseURL)!)
                } label: {
                    HStack(spacing: 12) {
                        Image(systemName: route.icon)
                            .font(.system(size: 15))
                            .foregroundColor(.gold)
                            .frame(width: 22)
                        Text(route.title)
                            .font(.inter(15))
                            .foregroundColor(.ivory)
                        Spacer()
                        Image(systemName: "chevron.right")
                            .font(.system(size: 12))
                            .foregroundColor(.goldDeep)
                    }
                }
                .buttonStyle(.plain)
                if idx < routes.count - 1 {
                    Divider().overlay(Color.borderSoft)
                }
            }
        }
    }
}
