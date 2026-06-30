import SwiftUI

/// The Library: a searchable grid of the text catalog. Tapping a text opens the
/// Explorer. Twilight Sanctum palette throughout.
///
/// Reskinned to the shipped-web look: true-black page, a Marcellus screen title,
/// and grid cards that mirror the web `TextCard` — true-black-leaning surface,
/// a gold-hairline border, a Marcellus text name, and uppercase-mono slate tag
/// capsules. Uses the `Theme` tokens (Color statics + Font helpers) throughout.
@available(iOS 15.0, *)
struct LibraryView: View {
    let service: LibraryService
    @StateObject private var vm: LibraryViewModel

    init(service: LibraryService) {
        self.service = service
        _vm = StateObject(wrappedValue: LibraryViewModel(service: service))
    }

    private let columns = [GridItem(.adaptive(minimum: 150), spacing: 12)]

    var body: some View {
        NavigationView {
            ZStack {
                Color.tsBlack.ignoresSafeArea()
                content
            }
            .sanctumNavigationTitle("Library")
        }
        .navigationViewStyle(.stack)
        .task { await vm.load() }
    }

    @ViewBuilder
    private var content: some View {
        if vm.isLoading && vm.texts.isEmpty {
            ProgressView().tint(.gold)
        } else if let error = vm.error, vm.texts.isEmpty {
            VStack(spacing: 12) {
                Text(error)
                    .font(.inter(15))
                    .foregroundColor(.slate)
                    .multilineTextAlignment(.center)
                Button("Retry") { Task { await vm.load() } }
                    .font(.inter(15, weight: .semibold))
                    .foregroundColor(.gold)
            }.padding()
        } else {
            ScrollView {
                LazyVGrid(columns: columns, spacing: 12) {
                    ForEach(vm.filtered) { text in
                        NavigationLink {
                            ExploreView(service: service, text: text)
                        } label: {
                            TextCard(text: text)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(16)
            }
            .searchable(text: $vm.query, prompt: "Search texts")
        }
    }
}

/// Native twin of the web `TextCard`: a dark surface panel on true black, a
/// gold hairline, a Marcellus text name, and mono slate tag capsules.
@available(iOS 15.0, *)
private struct TextCard: View {
    let text: PuranaRef

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(text.name)
                .font(.marcellus(16))
                .foregroundColor(.ivory)
                .lineLimit(2)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
            HStack(spacing: 6) {
                if let cat = text.category {
                    Tag(text: cat)
                }
                if let tr = text.tradition, tr != "mixed" {
                    Tag(text: tr)
                }
            }
        }
        .frame(maxWidth: .infinity, minHeight: 118, alignment: .topLeading)
        .padding(14)
        .background(Color.cardIndigo)
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(Color.white.opacity(0.06), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 16))
        // Gold reads as natural flame — a whisper of glow, never a halo.
        .shadow(color: Color.gold.opacity(0.06), radius: 8, y: 2)
    }
}

/// Uppercase-mono slate capsule — matches the web tag pills.
@available(iOS 15.0, *)
private struct Tag: View {
    let text: String
    var body: some View {
        Text(text)
            .uppercaseMonoLabel(size: 9, color: .slate, tracking: 0.14)
            .padding(.horizontal, 8).padding(.vertical, 4)
            .background(Color.tsBlack)
            .overlay(
                Capsule().strokeBorder(Color.slate.opacity(0.22), lineWidth: 1)
            )
            .clipShape(Capsule())
    }
}
