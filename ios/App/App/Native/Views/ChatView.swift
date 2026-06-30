import SwiftUI
import UIKit

/// Native SwiftUI chat screen. A single contemplative reading surface: the
/// answer is set directly onto the slowly-living Bindu field — no message
/// cards — and the transcript reads top-down, the newest question anchored to
/// the top of the view with its answer unspooling beneath it (not the usual
/// bottom-pinned chat log). Twilight Sanctum palette, TRUE BLACK base (mirrors
/// the SHIPPED web `globals.css :root` + `ChatInterface.tsx`).
struct ChatView: View {
    @ObservedObject private var vm: ChatViewModel
    /// Optional — enables the "related verses" lookup in the source detail sheet.
    private let library: LibraryService?
    @State private var selectedSource: SourceRef?
    @FocusState private var composerFocused: Bool

    /// VM is injected so the host (RootView) can observe `limitReached` and
    /// present the paywall when the backend returns 429.
    init(vm: ChatViewModel, library: LibraryService? = nil) {
        self.vm = vm
        self.library = library
    }

    var body: some View {
        ZStack {
            binduBackdrop
            if vm.messages.isEmpty {
                // Ceremonial entry — the web's empty-state hero: floated orb,
                // gold-gradient H1, danda divider, lineage hint, composer, chips.
                emptyHero
            } else {
                VStack(spacing: 0) {
                    transcript
                    composer
                }
            }
        }
        .sheet(item: $selectedSource) { source in
            SourceDetailView(source: source, service: library)
        }
    }

    /// The native Metal Bindu orb sits behind everything; its convergence is
    /// driven by chat activity via `vm.orbLevel` (wake on send, peak when
    /// sources land, settle when idle).
    ///
    /// CRITICAL: we do NOT lay a flat scrim plate over the orb — that washed the
    /// gold/teal/violet to grey. Instead the wash is dropped to a whisper and
    /// answer legibility is carried by a layered dark contact text-shadow on the
    /// answer `Text` itself (see `MessageView`). Never a card, never a plate.
    private var binduBackdrop: some View {
        BinduOrbView(level: vm.orbLevel)
            .ignoresSafeArea()
            .allowsHitTesting(false)
            .overlay(
                // A whisper only — keeps the void from feeling raw without
                // greying the orb. (Was Color(0x0A0810).opacity(0.35).)
                Color.tsBlack.opacity(0.10).ignoresSafeArea()
            )
    }

    /// The id of the most recent user turn. When it changes — a new question is
    /// asked — we glide that question to the TOP, so reading begins above and
    /// flows down. We deliberately do NOT chase the streaming tail to the bottom.
    private var lastUserID: String? {
        vm.messages.last(where: { $0.role == .user })?.id
    }

    private var transcript: some View {
        GeometryReader { geo in
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 28) {
                        ForEach(vm.messages) { msg in
                            MessageView(
                                message: msg,
                                onTapSource: { selectedSource = $0 },
                                onRegenerate: { Task { await vm.regenerate(msg.id) } }
                            )
                            .id(msg.id)
                        }
                        // Trailing breath — lets the newest question reach the very
                        // top of the view even while its answer is still short.
                        Color.clear
                            .frame(height: geo.size.height * 0.8)
                            .allowsHitTesting(false)
                    }
                    .padding(.horizontal, 22)
                    .padding(.top, 20)
                }
                .onChange(of: lastUserID) { id in
                    guard let id else { return }
                    withAnimation(.easeOut(duration: 0.45)) {
                        proxy.scrollTo(id, anchor: .top)
                    }
                }
            }
        }
    }

    // MARK: - Empty-state hero (ceremonial entry)

    private var emptyHero: some View {
        GeometryReader { geo in
            let orbSize = min(max(geo.size.height * 0.20, 120), 200)
            // Centred entry composition: orb → wordmark → tagline → composer, the
            // whole group floated to the MIDDLE of the screen (owner 2026-06-28).
            // The lineage line is gone from here — it now lives on the About page.
            // Top/bottom Spacers centre the block; the danda divider was dropped so
            // the entry reads as just "PuranGPT / Your Intention Matters".
            VStack(spacing: 0) {
                Spacer(minLength: 24)

                BinduOrbView(level: vm.orbLevel)
                    .frame(width: orbSize, height: orbSize)
                    .allowsHitTesting(false)

                // PuranGPT wordmark above the tagline.
                Text("PuranGPT")
                    .font(.marcellus(22))
                    .foregroundStyle(Color.goldBright)
                    .padding(.top, 16)

                // Gold-gradient Marcellus tagline.
                Text("Your Intention Matters")
                    .font(.marcellus(30))
                    .multilineTextAlignment(.center)
                    .overlay(
                        LinearGradient(
                            colors: [Color(hex: "#f1dda3"),
                                     Color(hex: "#e7cd84"),
                                     Color(hex: "#cba455")],
                            startPoint: .top, endPoint: .bottom
                        )
                        .mask(
                            Text("Your Intention Matters")
                                .font(.marcellus(30))
                                .multilineTextAlignment(.center)
                        )
                    )
                    .shadow(color: Color(hex: "#cba455").opacity(0.22), radius: 16)
                    .padding(.top, 6)
                    .padding(.horizontal, 24)

                // Suggestion chips sit ABOVE the composer so the keyboard can't bury
                // them (owner bug, 2026-06-28).
                suggestionChips
                    .padding(.top, 24)
                    .padding(.bottom, 12)

                composer
                    .frame(maxWidth: 560)

                Spacer(minLength: 24)
            }
            .frame(maxWidth: .infinity)
        }
    }

    /// Dim gold-brown lineage hint. `.tracking` is iOS16+, so apply it only when
    /// available (the deployment target is iOS 15) and fall back gracefully.
    @ViewBuilder
    private var lineageHint: some View {
        let base = Text("Under the discipleship of Sri Shailendra Sharma")
            .font(.marcellus(13))
            .foregroundColor(Color(hex: "#9c8150"))
        if #available(iOS 16.0, *) {
            base.tracking(0.9)
        } else {
            base
        }
    }

    private static let starterPrompts = [
        "What does the Gita say about duty?",
        "Tell me the story of Prahlada",
    ]

    private var suggestionChips: some View {
        HStack(spacing: 10) {
            ForEach(Self.starterPrompts, id: \.self) { prompt in
                Button {
                    vm.draft = prompt
                    Task { await vm.send() }
                } label: {
                    Text(prompt)
                        .font(.inter(13))
                        .foregroundStyle(Color.ivory.opacity(0.85))
                        .lineLimit(1)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 9)
                        .background(
                            Capsule().fill(Color.gold.opacity(0.06))
                        )
                        .overlay(
                            Capsule().strokeBorder(Color.gold.opacity(0.24), lineWidth: 1)
                        )
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, 18)
    }

    // MARK: - Composer

    private var composerActive: Bool {
        !vm.draft.trimmingCharacters(in: .whitespaces).isEmpty
    }

    private var composer: some View {
        VStack(spacing: 8) {
            if let status = vm.statusLine, vm.isStreaming {
                HStack(spacing: 8) {
                    ProgressView().scaleEffect(0.7).tint(Color.gold)
                    Text(status)
                        .uppercaseMonoLabel(size: 10, color: .slate)
                    Spacer()
                }
                .transition(.opacity)
            }

            HStack(spacing: 12) {
                // Deep-research toggle.
                Button {
                    vm.deepResearch.toggle()
                } label: {
                    Image(systemName: "binoculars.fill")
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(vm.deepResearch ? Color.tsBlack : Color.slate)
                        .frame(width: 38, height: 38)
                        .background(vm.deepResearch ? Color.gold : Color.gold.opacity(0.10))
                        .clipShape(Circle())
                }
                .accessibilityLabel(vm.deepResearch ? "Deep research on" : "Deep research off")

                TextField(vm.deepResearch ? "Research the texts…" : "What calls to you…",
                          text: $vm.draft)
                    .textFieldStyle(.plain)
                    .font(.inter(16))
                    .foregroundStyle(Color.ivory)
                    .lineLimit(1)
                    .focused($composerFocused)

                // Circular gold send button.
                Button {
                    Task { await vm.send() }
                } label: {
                    Image(systemName: vm.isStreaming ? "stop.fill" : "arrow.up")
                        .font(.system(size: 16, weight: .bold))
                        .foregroundStyle(Color(hex: "#1a1206"))
                        .frame(width: 40, height: 40)
                        .background(LinearGradient.goldButton)
                        .clipShape(Circle())
                        .goldGlow(.sm)
                }
                .disabled(vm.draft.trimmingCharacters(in: .whitespaces).isEmpty && !vm.isStreaming)
            }
            .padding(.horizontal, 8)
            .padding(.vertical, 7)
            .background(
                // Top→bottom dark gradient pill.
                RoundedRectangle(cornerRadius: 28)
                    .fill(
                        LinearGradient(
                            colors: [Color(hex: "#161618"), Color(hex: "#0d0d0f")],
                            startPoint: .top, endPoint: .bottom
                        )
                    )
            )
            .overlay(
                // Gold-hairline border — brightens when there's text.
                RoundedRectangle(cornerRadius: 28)
                    .strokeBorder(
                        composerActive ? Color.gold.opacity(0.35) : Color.gold.opacity(0.20),
                        lineWidth: 1
                    )
            )
            // Soft gold focus glow when text is present.
            .shadow(
                color: Color.gold.opacity(composerActive ? 0.22 : 0.0),
                radius: 14
            )
            .animation(.easeInOut(duration: 0.4), value: composerActive)
        }
        .padding(12)
        .animation(.easeInOut(duration: 0.2), value: vm.statusLine)
    }
}

// MARK: - Message (cardless)

/// One turn rendered directly onto the field — no bubble, no card. The seeker's
/// question floats as centred gold (a "ghost echo"); the answer is set as Inter
/// body in brighter ivory with a layered DARK contact shadow for legibility over
/// the orb; citations as uppercase-mono slate rows beneath it.
private struct MessageView: View {
    let message: ChatMessageVM
    /// Tapping a citation opens its verse-detail sheet.
    var onTapSource: (SourceRef) -> Void = { _ in }
    /// Re-run the question that produced this answer.
    var onRegenerate: () -> Void = {}

    var body: some View {
        if message.role == .user {
            // Ghost-echo question — restrained Marcellus 18pt at 0.85 opacity with
            // a capped focal glow (web echo: a quiet residue, not a headline).
            Text(message.content)
                .font(.marcellus(18))
                .foregroundStyle(Color.goldBright)
                .opacity(0.85)
                .goldGlow(.sm)
                .multilineTextAlignment(.center)
                .frame(maxWidth: .infinity, alignment: .center)
                .padding(.bottom, 2)
        } else {
            VStack(alignment: .leading, spacing: 12) {
                // Answer body — rendered markdown (headings, lists, quotes, code,
                // inline emphasis), Inter ~16pt ivory. Two stacked dark contact
                // shadows keep it readable over the live orb — NOT a plate.
                Group {
                    if message.error {
                        Text(message.content)
                            .font(.inter(16))
                            .lineSpacing(7)
                            .foregroundStyle(Color.red.opacity(0.9))
                    } else if message.content.isEmpty && message.pending {
                        Text("…")
                            .font(.inter(16))
                            .foregroundStyle(Color.ivoryBright)
                    } else {
                        MarkdownText(text: message.content)
                    }
                }
                .shadow(color: Color(hex: "#06040C").opacity(0.9), radius: 2)
                .shadow(color: Color(hex: "#06040C").opacity(0.9), radius: 10)
                .frame(maxWidth: .infinity, alignment: .leading)

                if !message.sources.isEmpty {
                    sourcesBlock
                }

                if !message.pending && !message.error && !message.content.isEmpty {
                    MessageActions(content: message.content, onRegenerate: onRegenerate)
                }
            }
        }
    }

    /// Numbered gold citation badges — taps open the verse-detail sheet. Mirrors
    /// the web's numbered inline citations.
    private var sourcesBlock: some View {
        VStack(alignment: .leading, spacing: 8) {
            Rectangle()
                .fill(Color.gold.opacity(0.15))
                .frame(height: 1)
                .padding(.bottom, 2)
            Text("Sources")
                .uppercaseMonoLabel(size: 9, color: .goldDeep, tracking: 0.16)
            ForEach(Array(message.sources.prefix(6).enumerated()), id: \.element.id) { idx, src in
                Button {
                    onTapSource(src)
                } label: {
                    HStack(spacing: 8) {
                        Text("\(idx + 1)")
                            .font(.inter(10, weight: .semibold))
                            .foregroundStyle(Color(hex: "#1a1206"))
                            .frame(width: 18, height: 18)
                            .background(Circle().fill(Color.gold.opacity(0.85)))
                        Text("\(src.textName) · \(src.reference)")
                            .font(.inter(12))
                            .foregroundStyle(Color.ivory.opacity(0.85))
                            .lineLimit(1)
                        Spacer(minLength: 0)
                        Image(systemName: "chevron.right")
                            .font(.system(size: 9))
                            .foregroundStyle(Color.slate)
                    }
                    .padding(.vertical, 6)
                    .padding(.horizontal, 9)
                    .background(RoundedRectangle(cornerRadius: 11).fill(Color.gold.opacity(0.05)))
                    .overlay(
                        RoundedRectangle(cornerRadius: 11)
                            .strokeBorder(Color.gold.opacity(0.16), lineWidth: 1)
                    )
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.top, 4)
    }
}

// MARK: - Message action row (copy / regenerate / feedback)

/// The action bar beneath a completed answer — mirrors the web ChatInterface.
/// Copy and Regenerate are functional; the thumbs are a local acknowledgement
/// (no feedback endpoint is wired yet).
private struct MessageActions: View {
    let content: String
    var onRegenerate: () -> Void = {}
    @State private var copied = false
    @State private var vote = 0   // -1 down · 0 none · +1 up

    var body: some View {
        HStack(spacing: 6) {
            pill(copied ? "checkmark" : "doc.on.doc", copied ? "Copied" : "Copy") {
                UIPasteboard.general.string = content
                withAnimation { copied = true }
            }
            pill("arrow.clockwise", "Regenerate") { onRegenerate() }
            Spacer(minLength: 0)
            thumb("hand.thumbsup", active: vote == 1) { vote = vote == 1 ? 0 : 1 }
            thumb("hand.thumbsdown", active: vote == -1) { vote = vote == -1 ? 0 : -1 }
        }
        .padding(.top, 2)
    }

    private func pill(_ system: String, _ label: String, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 4) {
                Image(systemName: system).font(.system(size: 10, weight: .medium))
                Text(label).font(.inter(11, weight: .medium))
            }
            .foregroundStyle(Color.slate)
            .padding(.vertical, 5)
            .padding(.horizontal, 9)
            .overlay(Capsule().strokeBorder(Color.gold.opacity(0.18), lineWidth: 1))
        }
        .buttonStyle(.plain)
    }

    private func thumb(_ system: String, active: Bool, _ action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: active ? "\(system).fill" : system)
                .font(.system(size: 12))
                .foregroundStyle(active ? Color.gold : Color.slate.opacity(0.7))
                .frame(width: 30, height: 28)
        }
        .buttonStyle(.plain)
    }
}

// MARK: - Minimal markdown rendering (dependency-free)

/// Renders answer markdown without an SPM dependency: blocks (headings, lists,
/// blockquotes, code, paragraphs) are parsed by line; inline emphasis
/// (**bold**, *italic*, `code`) is handled by iOS-15 `AttributedString(markdown:)`.
private struct MarkdownText: View {
    let text: String
    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            ForEach(Array(MDBlock.parse(text).enumerated()), id: \.offset) { _, block in
                block.view
            }
        }
    }
}

private enum MDBlock {
    case heading(Int, String)
    case quote(String)
    case bullet(String)
    case code(String)
    case paragraph(String)

    @ViewBuilder var view: some View {
        switch self {
        case .heading(let lvl, let s):
            mdInline(s,
                     font: .marcellus(lvl == 1 ? 21 : lvl == 2 ? 18 : 16),
                     color: lvl >= 3 ? Color.gold : Color.ivoryBright)
                .padding(.top, 2)
        case .quote(let s):
            mdInline(s, font: .inter(15), color: Color.ivory.opacity(0.82))
                .italic()
                .padding(.leading, 12)
                .overlay(alignment: .leading) {
                    Rectangle().fill(Color.gold.opacity(0.4)).frame(width: 2)
                }
        case .bullet(let s):
            HStack(alignment: .top, spacing: 8) {
                Text("•").font(.inter(16)).foregroundColor(.gold)
                mdInline(s, font: .inter(16), color: Color.ivoryBright)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        case .code(let s):
            Text(s)
                .font(.system(size: 13, design: .monospaced))
                .foregroundColor(.ivory.opacity(0.9))
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(10)
                .background(RoundedRectangle(cornerRadius: 8).fill(Color.tsBlack.opacity(0.6)))
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .strokeBorder(Color.gold.opacity(0.12), lineWidth: 1)
                )
        case .paragraph(let s):
            mdInline(s, font: .inter(16), color: Color.ivoryBright)
                .lineSpacing(7)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    static func parse(_ raw: String) -> [MDBlock] {
        var blocks: [MDBlock] = []
        var para: [String] = []
        var code: [String] = []
        var inCode = false
        func flush() {
            if !para.isEmpty {
                blocks.append(.paragraph(para.joined(separator: " ")))
                para.removeAll()
            }
        }
        for line in raw.components(separatedBy: "\n") {
            let t = line.trimmingCharacters(in: .whitespaces)
            if t.hasPrefix("```") {
                if inCode {
                    blocks.append(.code(code.joined(separator: "\n")))
                    code.removeAll(); inCode = false
                } else {
                    flush(); inCode = true
                }
                continue
            }
            if inCode { code.append(line); continue }
            if t.isEmpty { flush(); continue }
            if t.hasPrefix("### ") { flush(); blocks.append(.heading(3, String(t.dropFirst(4)))); continue }
            if t.hasPrefix("## ")  { flush(); blocks.append(.heading(2, String(t.dropFirst(3)))); continue }
            if t.hasPrefix("# ")   { flush(); blocks.append(.heading(1, String(t.dropFirst(2)))); continue }
            if t.hasPrefix("> ")   { flush(); blocks.append(.quote(String(t.dropFirst(2)))); continue }
            if t.hasPrefix("- ") || t.hasPrefix("* ") {
                flush(); blocks.append(.bullet(String(t.dropFirst(2)))); continue
            }
            if let r = t.range(of: "^[0-9]+\\.\\s", options: .regularExpression) {
                flush(); blocks.append(.bullet(String(t[r.upperBound...]))); continue
            }
            para.append(t)
        }
        if inCode && !code.isEmpty { blocks.append(.code(code.joined(separator: "\n"))) }
        flush()
        return blocks
    }
}

private func mdInline(_ s: String, font: Font, color: Color) -> Text {
    if let attr = try? AttributedString(
        markdown: s,
        options: AttributedString.MarkdownParsingOptions(
            interpretedSyntax: .inlineOnlyPreservingWhitespace
        )
    ) {
        return Text(attr).font(font).foregroundColor(color)
    }
    return Text(s).font(font).foregroundColor(color)
}

extension Color {
    /// Hex initializer so we can use the exact Twilight Sanctum tokens.
    init(hex: UInt32) {
        self.init(
            .sRGB,
            red:   Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8)  & 0xFF) / 255,
            blue:  Double(hex & 0xFF) / 255,
            opacity: 1
        )
    }
}
