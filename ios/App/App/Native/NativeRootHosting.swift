import UIKit
import SwiftUI

/// Bridges the native SwiftUI `RootView` into the existing UIKit app without
/// ripping out the Capacitor shell. Integration is **flag-gated** so the
/// shipping WebView app is untouched until we deliberately flip the switch.
///
/// Flip mechanism (in order of precedence):
///   1. Launch argument `-NativeUI` (Xcode scheme env, for local testing).
///   2. Info.plist boolean `UseNativeUI` (per-build, for a TestFlight cohort).
/// Default: false → Capacitor WebView, exactly as it ships today.
enum NativeUI {
    static var isEnabled: Bool {
        if ProcessInfo.processInfo.arguments.contains("-NativeUI") { return true }
        if let v = Bundle.main.object(forInfoDictionaryKey: "UseNativeUI") as? Bool { return v }
        return false
    }

    /// The root view controller to install when native UI is enabled.
    static func makeRootViewController() -> UIViewController {
        UIHostingController(rootView: RootView())
    }
}
