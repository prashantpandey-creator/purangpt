import SwiftUI

/// The Explorer: an AI-guided introduction to a single text — tagline, what it
/// is, why it matters, famous stories, and entry chapters for a newcomer.
///
/// Reskinned to the Twilight Sanctum look: true-black page, Marcellus tagline /
/// title register, uppercase-mono section labels, and dark `surface` cards with
/// gold hairlines for the story / chapter entries. `Theme` tokens throughout.
@available(iOS 15.0, *)
struct ExploreView: View {
    let service: LibraryService
    let text: PuranaRef
    @State private var intro: ExploreIntro?
    @State private var isLoading = true
    @State private var error: String?

    var body: some View {
        ZStack {
            Color.tsBlack.ignoresSafeArea()
            if isLoading {
                VStack(spacing: 12) {
                    ProgressView().tint(.gold)
                    Text("Summoning the guide…")
                        .font(.inter(13))
                        .foregroundColor(.slate)
                }
            } else if let intro {
                body(for: intro)
            } else {
                VStack(spacing: 12) {
                    Text(error ?? "Couldn't load this text.")
                        .font(.inter(15))
                        .foregroundColor(.slate)
                        .multilineTextAlignment(.center)
                    Button("Retry") { Task { await load() } }
                        .font(.inter(15, weight: .semibold))
                        .foregroundColor(.gold)
                }.padding()
            }
        }
        .sanctumNavigationTitle(text.name)
        .task { await load() }
    }

    private func body(for intro: ExploreIntro) -> some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 26) {
                Text(text.name)
                    .font(.marcellus(28))
                    .foregroundColor(.goldBright)

                if let tagline = intro.tagline {
                    Text(tagline)
                        .font(.marcellus(19))
                        .italic()
                        .foregroundColor(.gold)
                }
                section("What it is", intro.whatItIs)
                section("Why it matters", intro.whyItMatters)

                if let stories = intro.famousStories, !stories.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        sectionTitle("Famous stories")
                        ForEach(stories) { story in
                            VStack(alignment: .leading, spacing: 6) {
                                HStack(alignment: .firstTextBaseline) {
                                    Text(story.title)
                                        .font(.marcellus(17))
                                        .foregroundColor(.ivory)
                                    if let hint = story.chapterHint {
                                        Text(hint)
                                            .uppercaseMonoLabel(size: 9, color: .slate, tracking: 0.14)
                                    }
                                }
                                if let d = story.description {
                                    Text(d)
                                        .font(.inter(14))
                                        .foregroundColor(.ivory.opacity(0.82))
                                }
                            }
                            .padding(14)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color.cardIndigo)
                            .overlay(
                                RoundedRectangle(cornerRadius: 14)
                                    .strokeBorder(Color.borderSoft, lineWidth: 1)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 14))
                        }
                    }
                }

                if let chapters = intro.entryChapters, !chapters.isEmpty {
                    VStack(alignment: .leading, spacing: 12) {
                        sectionTitle("Where to start")
                        ForEach(chapters) { ch in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(ch.label ?? ch.chapterHint ?? "Entry point")
                                    .font(.inter(15, weight: .semibold))
                                    .foregroundColor(.gold)
                                if let hint = ch.chapterHint {
                                    Text(hint)
                                        .uppercaseMonoLabel(size: 9, color: .slate, tracking: 0.14)
                                }
                                if let who = ch.forReader {
                                    Text("For \(who)")
                                        .font(.inter(13))
                                        .foregroundColor(.ivory.opacity(0.65))
                                }
                            }
                            // Web 'Where to start' renders each entry as a card,
                            // not bare text — give them the indigo card chrome.
                            .padding(12)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(Color.cardIndigo)
                            .overlay(
                                RoundedRectangle(cornerRadius: 12)
                                    .strokeBorder(Color.borderSoft, lineWidth: 1)
                            )
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                        }
                    }
                }

                if let pitch = intro.oneLinePitch {
                    Text("“\(pitch)”")
                        .font(.marcellus(17))
                        .italic()
                        .foregroundColor(.slate)
                        .padding(.top, 8)
                }
            }
            .padding(20)
        }
    }

    @ViewBuilder
    private func section(_ title: String, _ body: String?) -> some View {
        if let body, !body.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                sectionTitle(title)
                Text(body)
                    .font(.inter(15))
                    .foregroundColor(.ivoryBright.opacity(0.9))
            }
        }
    }

    private func sectionTitle(_ t: String) -> some View {
        Text(t)
            .uppercaseMonoLabel(size: 11, color: .goldDeep, tracking: 0.18)
    }

    private func load() async {
        isLoading = true; error = nil
        do {
            intro = try await service.intro(for: text.id)
        } catch {
            self.error = "The guide is resting. \(error.localizedDescription)"
        }
        isLoading = false
    }
}
