import SwiftUI

/// Past conversations (`/api/sessions`). Tapping one loads it back into the chat
/// transcript; swipe to delete. Presented as a sheet from the chat header.
///
/// Reskinned to the Twilight Sanctum look: true-black page, the system grouped
/// `List` background hidden and rows dressed as dark surface cards with a
/// gold-deep hairline, Marcellus session titles, and uppercase-mono timestamps.
/// The `List` itself is retained ONLY for native swipe-to-delete. `Theme` tokens
/// throughout.
@available(iOS 15.0, *)
struct HistoryView: View {
    let service: LibraryService
    /// Called with a loaded history when the user picks a session.
    let onPick: (SessionHistory) -> Void
    @Environment(\.dismiss) private var dismiss

    @State private var sessions: [SessionSummary] = []
    @State private var isLoading = true
    @State private var error: String?
    @State private var loadingID: String?

    var body: some View {
        NavigationView {
            ZStack {
                Color.tsBlack.ignoresSafeArea()
                content
            }
            .sanctumNavigationTitle("History")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Done") { dismiss() }
                        .font(.inter(15, weight: .semibold))
                        .foregroundColor(.gold)
                }
            }
        }
        .navigationViewStyle(.stack)
        .task { await load() }
    }

    @ViewBuilder
    private var content: some View {
        if isLoading {
            ProgressView().tint(.gold)
        } else if sessions.isEmpty {
            VStack(spacing: 10) {
                Image(systemName: "clock.arrow.circlepath")
                    .font(.largeTitle)
                    .foregroundColor(.goldDeep)
                Text(error ?? "No past conversations yet.")
                    .font(.inter(15))
                    .foregroundColor(.slate)
                    .multilineTextAlignment(.center)
            }.padding()
        } else {
            List {
                ForEach(sessions) { s in
                    Button { Task { await pick(s) } } label: {
                        sessionRow(s)
                    }
                    .buttonStyle(.plain)
                    .listRowBackground(Color.clear)
                    .listRowSeparator(.hidden)
                    .listRowInsets(EdgeInsets(top: 5, leading: 16, bottom: 5, trailing: 16))
                }
                .onDelete(perform: delete)
            }
            .listStyle(.plain)
            .scrollContentBackgroundCompat()
        }
    }

    private func sessionRow(_ s: SessionSummary) -> some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 5) {
                Text(s.title)
                    .font(.marcellus(17))
                    .foregroundColor(.ivory)
                    .lineLimit(1)
                Text(relativeDate(s.updatedAt))
                    .uppercaseMonoLabel(size: 9, color: .dimLabel, tracking: 0.16)
            }
            Spacer()
            if loadingID == s.id {
                ProgressView().scaleEffect(0.7).tint(.gold)
            } else {
                Image(systemName: "chevron.right")
                    .font(.system(size: 12))
                    .foregroundColor(.goldDeep)
            }
        }
        .padding(.vertical, 12)
        .padding(.leading, 12)
        .padding(.trailing, 4)
        .frame(maxWidth: .infinity, alignment: .leading)
        .contentShape(Rectangle())
        // Web sidebar = a compact text list with a left gold accent rule + a
        // hairline divider — NOT a heavy brown/indigo card.
        .overlay(alignment: .leading) {
            Rectangle().fill(Color.gold.opacity(0.30)).frame(width: 2)
        }
        .overlay(alignment: .bottom) {
            Rectangle().fill(Color.gold.opacity(0.08)).frame(height: 1)
        }
    }

    private func load() async {
        isLoading = true; error = nil
        do {
            sessions = try await service.sessions()
        } catch {
            self.error = "Couldn't load history."
        }
        isLoading = false
    }

    private func pick(_ s: SessionSummary) async {
        loadingID = s.id
        defer { loadingID = nil }
        do {
            let history = try await service.sessionHistory(s.id)
            onPick(history)
            dismiss()
        } catch {
            self.error = "Couldn't open that conversation."
        }
    }

    private func delete(at offsets: IndexSet) {
        let toDelete = offsets.map { sessions[$0] }
        sessions.remove(atOffsets: offsets)
        Task {
            for s in toDelete {
                try? await service.deleteSession(s.id)
            }
        }
    }

    private func relativeDate(_ ts: Double) -> String {
        let date = Date(timeIntervalSince1970: ts)
        let fmt = RelativeDateTimeFormatter()
        fmt.unitsStyle = .abbreviated
        return fmt.localizedString(for: date, relativeTo: Date())
    }
}

private extension View {
    @ViewBuilder
    func scrollContentBackgroundCompat() -> some View {
        if #available(iOS 16.0, *) { self.scrollContentBackground(.hidden) }
        else { self }
    }
}
