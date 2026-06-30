import SwiftUI
import WebKit

/// A WKWebView wrapper for the long-tail routes that don't earn a native rewrite
/// (blog, docs, legal, about, etc.). These are public, read-mostly pages — the
/// native shell hosts them so users never bounce to Safari, but we don't pay to
/// rebuild them in SwiftUI.
///
/// Loads `${baseURL}${path}`. A thin loading + error overlay keeps it from
/// looking like a dead white rectangle while the page fetches.
struct WebRouteView: View {
    let title: String
    let url: URL

    @State private var isLoading = true
    @State private var failed = false

    var body: some View {
        ZStack {
            Color(hex: 0x0A0810).ignoresSafeArea()
            WebView(url: url, isLoading: $isLoading, failed: $failed)
                .opacity(failed ? 0 : 1)

            if isLoading && !failed {
                ProgressView().tint(Color(hex: 0xCBA455))
            }
            if failed {
                VStack(spacing: 10) {
                    Text("Couldn't load this page.")
                        .foregroundStyle(Color(hex: 0x7E92B8))
                    Text(url.absoluteString)
                        .font(.caption2)
                        .foregroundStyle(Color(hex: 0x7E92B8).opacity(0.6))
                }
            }
        }
        .sanctumNavigationTitle(title)
    }
}

/// UIViewRepresentable bridge to WKWebView. Reports load/finish/fail back to the
/// SwiftUI overlay via bindings.
private struct WebView: UIViewRepresentable {
    let url: URL
    @Binding var isLoading: Bool
    @Binding var failed: Bool

    func makeCoordinator() -> Coordinator { Coordinator(self) }

    func makeUIView(context: Context) -> WKWebView {
        let config = WKWebViewConfiguration()
        let web = WKWebView(frame: .zero, configuration: config)
        web.navigationDelegate = context.coordinator
        web.isOpaque = false
        web.backgroundColor = UIColor(red: 0x0A/255, green: 0x08/255, blue: 0x10/255, alpha: 1)
        web.scrollView.backgroundColor = web.backgroundColor
        web.load(URLRequest(url: url))
        return web
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKNavigationDelegate {
        let parent: WebView
        init(_ parent: WebView) { self.parent = parent }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
            parent.isLoading = true; parent.failed = false
        }
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            parent.isLoading = false
        }
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            parent.isLoading = false; parent.failed = true
        }
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            parent.isLoading = false; parent.failed = true
        }
    }
}
