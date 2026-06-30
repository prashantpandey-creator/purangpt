import SwiftUI
import UIKit

/// Tier-0 design foundation for the native PuranGPT UI.
///
/// **Source of truth:** the SHIPPED web `src/app/globals.css :root` (the
/// "Twilight Sanctum" palette). The older `#0A0810` base in legacy native code
/// and the CLAUDE.md doc are STALE — the real page base is TRUE BLACK.
///
/// Everything visual downstream (chat, sidebar, dashboard) consumes these
/// tokens, so they must match the web exactly. Raw hex must never appear in
/// feature views — reach for these statics instead.
///
/// Fonts (Marcellus + Inter) are bundled under `Native/Fonts/` and registered
/// in Info.plist `UIAppFonts`. We address them by their exact PostScript names
/// so they never silently fall back to system faces. See `Theme.fontsAreLoaded`
/// for the runtime guard / diagnostic.

// MARK: - Palette

extension Color {
    /// Convenience hex initializer (supports `RRGGBB` and `RRGGBBAA`).
    init(hex: String) {
        let s = hex.trimmingCharacters(in: CharacterSet(charactersIn: "#"))
        var v: UInt64 = 0
        Scanner(string: s).scanHexInt64(&v)
        let r, g, b, a: Double
        switch s.count {
        case 8: // RRGGBBAA
            r = Double((v >> 24) & 0xFF) / 255
            g = Double((v >> 16) & 0xFF) / 255
            b = Double((v >> 8) & 0xFF) / 255
            a = Double(v & 0xFF) / 255
        default: // RRGGBB (and any malformed string → opaque)
            r = Double((v >> 16) & 0xFF) / 255
            g = Double((v >> 8) & 0xFF) / 255
            b = Double(v & 0xFF) / 255
            a = 1
        }
        self.init(.sRGB, red: r, green: g, blue: b, opacity: a)
    }

    // ── Base / surfaces ──────────────────────────────────────────────────
    /// True black — the OLED page base (`--bg-deep` / `--dark-bg` = #000000).
    static let tsBlack    = Color(hex: "#000000")
    /// Faintly raised neutral panel (`--surface` = #0e0e11).
    static let surface1   = Color(hex: "#0e0e11")
    /// Warm raised panel (`--surface-1` = #15120e).
    static let surface2   = Color(hex: "#15120e")
    /// Inputs / menus / elevated panels (`--surface-2` = #1c1815).
    static let surface3   = Color(hex: "#1c1815")

    // ── Gold (primary accent) — ROLE CONTRACT (enforce app-wide) ─────────
    //   gold       → protagonist text accent + headings (the default gold).
    //   goldBright → SMALL focal GLINTS only, or the top stop of a gradient.
    //   goldDeep   → hairlines / borders ONLY (never headings).
    // Inverting these (goldBright on big fills, goldDeep on headings) is the
    // recurring "accent inversion" bug the design audit flagged — do not.
    /// Candlelit gold — protagonist text accent + headings (`--gold` = #cba455).
    static let gold       = Color(hex: "#cba455")
    /// Warm flame highlight — SMALL focal glints / gradient top-stop (`--gold-bright` = #e7cd84).
    static let goldBright = Color(hex: "#e7cd84")
    /// Aged brass — hairlines / borders ONLY (`--gold-deep` = #b8893b).
    static let goldDeep   = Color(hex: "#b8893b")

    // ── Cool accent (the ONLY one) ───────────────────────────────────────
    /// Moonlit slate — cool secondary (`--slate` = #7e92b8).
    static let slate      = Color(hex: "#7e92b8")

    // ── Text ─────────────────────────────────────────────────────────────
    /// Sandalwood ivory — sacred text (`--ivory` = #e2d4b2).
    static let ivory      = Color(hex: "#e2d4b2")
    /// Brighter answer body text (#e8e1d4).
    static let ivoryBright = Color(hex: "#e8e1d4")
    /// Dim label tone (#a38d7c).
    static let dimLabel   = Color(hex: "#a38d7c")
    /// Dimmer label tone (#998871).
    static let dimLabel2  = Color(hex: "#998871")
    /// Warm pale gold for Devanagari / Sanskrit lines (`--sanskrit-text` = #ffe0b3).
    static let sanskrit   = Color(hex: "#ffe0b3")

    // ── Hairline border ──────────────────────────────────────────────────
    /// Warm gold hairline (`--border-soft` = rgba(212,175,55,0.12)).
    static let borderSoft = Color(hex: "#d4af37").opacity(0.12)

    // ── Web card / indigo surfaces (the REAL web component tones) ─────────
    // The audit found surface2 (#15120e, warm brown) overused where the web
    // renders neutral/indigo. These are the actual web tones; repoint card/
    // panel consumers at the token matching the web component they mirror.
    /// Indigo chat/explore card base (web explore/chat card = #141121).
    static let cardIndigo        = Color(hex: "#141121")
    /// Indigo card pressed / active (#1a1630).
    static let cardIndigoPressed = Color(hex: "#1a1630")
    /// Indigo Pro / elevated panel (web Pro card `--surface-2` = #16131F).
    static let surfaceIndigo     = Color(hex: "#16131F")
    /// Neutral elevated / assistant-bubble surface (web #141416).
    static let surfaceBubble     = Color(hex: "#141416")
}

// MARK: - Gold CTA fill (the web's candlelit gradient — never a flat gold button)

extension LinearGradient {
    /// Candlelit gold CTA fill — the web's `linear-gradient(135deg,#e7cd84,#cba455)`.
    /// Use on every primary gold button instead of a flat `Color.gold` fill so CTAs
    /// carry the same warm depth as the web (the audit's flat-vs-gradient fix).
    static let goldButton = LinearGradient(
        colors: [Color.goldBright, Color.gold],
        startPoint: .topLeading, endPoint: .bottomTrailing
    )
}

// MARK: - Fonts

/// The exact PostScript names the bundled faces register under. Using these
/// (not the family name) is what guarantees the correct weight loads — Inter's
/// non-Regular weights expose distinct *family* names ("Inter Medium" etc.), so
/// addressing by PostScript name is the only reliable path.
enum FontName {
    static let marcellus      = "Marcellus-Regular"
    static let interRegular   = "Inter-Regular"
    static let interMedium    = "Inter-Medium"
    static let interSemiBold  = "Inter-SemiBold"
}

extension Font {
    /// Display face — Marcellus (titles, wordmark, ghost-echo questions,
    /// headings). Falls back to the system serif if the bundle font is missing.
    static func marcellus(_ size: CGFloat) -> Font {
        if Theme.isRegistered(FontName.marcellus) {
            return .custom(FontName.marcellus, size: size)
        }
        return .system(size: size, design: .serif)
    }

    /// Body face — Inter, addressed by exact PostScript name per weight so the
    /// right cut loads. Falls back to the matching system weight if missing.
    static func inter(_ size: CGFloat, weight: Font.Weight = .regular) -> Font {
        let psName: String
        switch weight {
        case .medium:
            psName = FontName.interMedium
        case .semibold, .bold, .heavy, .black:
            psName = FontName.interSemiBold
        default:
            psName = FontName.interRegular
        }
        if Theme.isRegistered(psName) {
            return .custom(psName, size: size)
        }
        return .system(size: size, weight: weight, design: .default)
    }
}

// MARK: - Uppercase mono tracked label modifier

/// The UPPERCASE tracked label style for citations, timestamps, mode-tags, and
/// "Trending today" — ~0.18em tracking, uppercased.
///
/// CRITICAL: this renders in **Inter Medium** (a bundled face), NOT
/// `.system(design: .monospaced)`. SF Mono was the single largest "generic iOS"
/// tell in the app — one line here leaked the OS system font into every label
/// app-wide (the design audit's #1 cross-cutting bug). The web uses Geist Mono
/// for this register; until that .ttf is bundled, Inter (already loaded,
/// tracked + uppercased) is the correct intentional stand-in. NEVER route this
/// through a system face again.
extension View {
    /// Apply the uppercase tracked label style (citations / timestamps /
    /// mode-tags / "Trending today"). Default tracking ≈ 0.18em.
    @ViewBuilder
    func uppercaseMonoLabel(
        size: CGFloat = 11,
        color: Color = .dimLabel,
        tracking: CGFloat = 0.18
    ) -> some View {
        // `.tracking` is iOS 16+; applied when available, gracefully omitted
        // below it (uppercase + the loaded Inter face still read correctly).
        if #available(iOS 16.0, *) {
            self
                .font(.inter(size, weight: .medium))
                .textCase(.uppercase)
                .tracking(size * tracking)
                .foregroundColor(color)
        } else {
            self
                .font(.inter(size, weight: .medium))
                .textCase(.uppercase)
                .foregroundColor(color)
        }
    }
}

// MARK: - Gold glow (capped focal glow — the restraint law's enforcement point)

/// The ONLY sanctioned way to apply a gold glow. Mirrors the web glow tokens and
/// HARD-CAPS alpha at 0.30 (the aesthetic law's ceiling). Glow is reserved for
/// focal points (logo, title, primary CTA) — never sprayed on every element. The
/// audit found three screens already over the cap and alpha drifting 0.06→0.35
/// view-to-view; routing every glow through this makes that impossible.
enum GlowTier {
    /// Resting button / passive focal — web `0 0 8px rgba(gold,0.12)`.
    case restingButton
    /// Small focal glow — web `--glow-gold-sm` (0.22 @ 8px).
    case sm
    /// Medium focal glow — web `--glow-gold-md` (0.30 @ 14px) — the ceiling.
    case md

    var alpha: Double {
        switch self {
        case .restingButton: return 0.12
        case .sm:            return 0.22
        case .md:            return 0.30
        }
    }
    var radius: CGFloat {
        switch self {
        case .restingButton: return 8
        case .sm:            return 8
        case .md:            return 14
        }
    }
}

extension View {
    /// Apply a capped gold focal glow. Replaces every hand-rolled
    /// `.shadow(color: .gold.opacity(x))` so alpha can never drift past 0.30.
    func goldGlow(_ tier: GlowTier = .sm, y: CGFloat = 0) -> some View {
        shadow(color: Color.gold.opacity(tier.alpha), radius: tier.radius, x: 0, y: y)
    }
}

// MARK: - Sanctum navigation title (Marcellus principal title — never SF Pro)

extension View {
    /// Replace the system `.navigationTitle` (which renders the screen's most
    /// prominent text in SF Pro — a generic-iOS tell) with a Marcellus gold
    /// title in the bar's principal slot. Use on EVERY screen instead of
    /// `.navigationTitle`. Requires an enclosing NavigationView/Stack.
    func sanctumNavigationTitle(_ title: String) -> some View {
        self
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .principal) {
                    Text(title)
                        .font(.marcellus(18))
                        .foregroundStyle(Color.gold)
                        .goldGlow(.sm)
                }
            }
    }
}

// MARK: - Font registration guard / diagnostics

enum Theme {
    /// Is a font with this PostScript name currently registered with the
    /// system? Used so `Font.marcellus` / `Font.inter` never silently fall
    /// back to a system face without us knowing.
    static func isRegistered(_ postScriptName: String) -> Bool {
        UIFont(name: postScriptName, size: 12) != nil
    }

    /// True only when ALL bundled faces resolved. If false, the .ttf bundling
    /// / Info.plist `UIAppFonts` wiring is broken and the UI is on fallbacks.
    static var fontsAreLoaded: Bool {
        [
            FontName.marcellus,
            FontName.interRegular,
            FontName.interMedium,
            FontName.interSemiBold,
        ].allSatisfy(isRegistered)
    }

    /// One-shot diagnostic — call early (e.g. in app launch under DEBUG) to log
    /// whether the bundled fonts loaded. Prints the resolved family names so a
    /// silent system fallback is visible in the console.
    static func logFontStatus() {
        for ps in [FontName.marcellus, FontName.interRegular,
                   FontName.interMedium, FontName.interSemiBold] {
            if let f = UIFont(name: ps, size: 12) {
                print("[Theme] font OK: \(ps) → familyName=\(f.familyName)")
            } else {
                print("[Theme] font MISSING (system fallback in use): \(ps)")
            }
        }
    }
}
