import Foundation

/// Loads the catalog once and filters it client-side by the search query.
@MainActor
final class LibraryViewModel: ObservableObject {
    @Published var texts: [PuranaRef] = []
    @Published var query: String = ""
    @Published var isLoading = false
    @Published var error: String?

    private let service: LibraryService

    init(service: LibraryService) { self.service = service }

    var filtered: [PuranaRef] {
        let q = query.trimmingCharacters(in: .whitespaces).lowercased()
        guard !q.isEmpty else { return texts }
        return texts.filter {
            $0.name.lowercased().contains(q)
            || ($0.tradition?.lowercased().contains(q) ?? false)
            || ($0.category?.lowercased().contains(q) ?? false)
        }
    }

    func load() async {
        guard texts.isEmpty else { return }   // load once
        isLoading = true; error = nil
        do {
            texts = try await service.catalog()
        } catch {
            self.error = "Couldn't load the library. \(error.localizedDescription)"
        }
        isLoading = false
    }
}
