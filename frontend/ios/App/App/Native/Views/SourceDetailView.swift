import SwiftUI

/// A verse-detail sheet opened by tapping a citation under an assistant message.
/// The SourceRef already carries the full passage (`text`), so the core view
/// needs no network round-trip. "Related verses" lazily fetches
/// /api/verses/{chunk_id}/similar when the user asks for it.
///
/// Reskinned to the Twilight Sanctum look: true-black sheet, a Marcellus
/// citation header, uppercase-mono meta tags, a sandalwood passage on a dark
/// surface card with a gold hairline, and surface cards for related verses.
/// `Theme` tokens throughout.
@available(iOS 15.0, *)
struct SourceDetailView: View {
    let source: SourceRef
    let service: LibraryService?   // optional: enables "related verses"
    @Environment(\.dismiss) private var dismiss

    @State private var related: [SimilarVerse] = []
    @State private var loadingRelated = false
    @State private var relatedError: String?

    var body: some View {
        NavigationView {
            ZStack {
                Color.tsBlack.ignoresSafeArea()
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        citationHeader
                        passage
                        meta
                        if service != nil, source.chunkId != nil {
                            relatedSection
                        }
                    }
                    .padding(20)
                }
            }
            .sanctumNavigationTitle(source.textName)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                        .font(.inter(15, weight: .semibold))
                        .foregroundColor(.gold)
                }
            }
        }
        .navigationViewStyle(.stack)
    }

    private var citationHeader: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(source.reference)
                .font(.marcellus(22))
                .foregroundColor(.goldBright)
            if !source.verseRange.isEmpty {
                Text("Verse \(source.verseRange)")
                    .uppercaseMonoLabel(size: 10, color: .slate, tracking: 0.16)
            }
        }
    }

    private var passage: some View {
        // Source text can carry HTML entities / GRETIL markup; show as-is but
        // selectable so a scholar can copy the Sanskrit.
        Text(source.text)
            .font(.inter(16))
            .foregroundColor(.ivory)
            .lineSpacing(4)
            .textSelection(.enabled)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(16)
            .background(Color.cardIndigo)
            .overlay(
                RoundedRectangle(cornerRadius: 14)
                    .strokeBorder(Color.goldDeep.opacity(0.22), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 14))
    }

    private var meta: some View {
        HStack(spacing: 8) {
            if !source.language.isEmpty { metaTag(source.language) }
            if let tr = source.tradition, !tr.isEmpty { metaTag(tr) }
            if let ed = source.edition, !ed.isEmpty { metaTag(ed) }
        }
    }

    private func metaTag(_ t: String) -> some View {
        Text(t)
            .uppercaseMonoLabel(size: 9, color: .slate, tracking: 0.14)
            .padding(.horizontal, 8).padding(.vertical, 4)
            .background(Color.tsBlack)
            .overlay(
                Capsule().strokeBorder(Color.slate.opacity(0.22), lineWidth: 1)
            )
            .clipShape(Capsule())
    }

    @ViewBuilder
    private var relatedSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            if related.isEmpty && !loadingRelated {
                Button {
                    Task { await loadRelated() }
                } label: {
                    Label("Find related verses", systemImage: "sparkle.magnifyingglass")
                        .font(.inter(15, weight: .medium))
                        .foregroundColor(.gold)
                }
            } else if loadingRelated {
                HStack(spacing: 8) {
                    ProgressView().scaleEffect(0.8).tint(.gold)
                    Text("Searching the corpus…")
                        .font(.inter(13))
                        .foregroundColor(.slate)
                }
            }

            if let relatedError {
                Text(relatedError)
                    .font(.inter(13))
                    .foregroundColor(.slate)
            }

            if !related.isEmpty {
                Text("Related verses")
                    .uppercaseMonoLabel(size: 11, color: .goldDeep, tracking: 0.18)
                    .padding(.top, 4)
            }

            ForEach(related) { r in
                VStack(alignment: .leading, spacing: 4) {
                    Text(r.reference ?? r.purana ?? r.id)
                        .uppercaseMonoLabel(size: 10, color: .gold, tracking: 0.14)
                    Text(r.text)
                        .font(.inter(13))
                        .foregroundColor(.ivory.opacity(0.72))
                        .lineLimit(3)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(12)
                .background(Color.cardIndigo)
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(Color.goldDeep.opacity(0.18), lineWidth: 1)
                )
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
    }

    private func loadRelated() async {
        guard let service, let chunkId = source.chunkId else { return }
        loadingRelated = true; relatedError = nil
        do {
            related = try await service.similarVerses(chunkId)
            if related.isEmpty { relatedError = "No related verses found." }
        } catch {
            relatedError = "Couldn't load related verses."
        }
        loadingRelated = false
    }
}
