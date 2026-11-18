import Foundation

/// Owns the retrieval playground: the search form state and its results.
@MainActor
final class SearchController: ObservableObject {
    @Published var query = ""
    @Published var strategy: RetrievalStrategy = .hybrid
    @Published var rerank = true
    @Published var mmr = false
    @Published var topK = 5
    @Published var fileType = ""
    @Published private(set) var results: [SearchResult] = []
    @Published private(set) var statsSummary = ""
    @Published private(set) var isLoading = false
    @Published var errorMessage: String?

    func runSearch(baseURL: URL) async {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isLoading else { return }

        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        let fileTypeFilter = fileType
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
        let filters = fileTypeFilter.isEmpty
            ? nil
            : Filters(fileType: fileTypeFilter)
        let request = SearchRequest(
            query: trimmed,
            strategy: strategy,
            rerank: rerank,
            mmr: mmr,
            topK: topK,
            filters: filters)

        do {
            let client = LocalRAGClient(baseURL: baseURL)
            let response = try await client.search(request)
            results = response.results
            statsSummary = response.statsSummary
        } catch {
            results = []
            statsSummary = ""
            errorMessage = (error as? LocalizedError)?.errorDescription
                ?? error.localizedDescription
        }
    }
}
