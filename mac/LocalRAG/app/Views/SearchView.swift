import SwiftUI

/// The retrieval playground: run a search with an explicit strategy,
/// reranking, and top-k, and inspect the ranked chunks.
struct SearchView: View {
    @EnvironmentObject private var settings: SettingsStore
    @EnvironmentObject private var searchController: SearchController

    var body: some View {
        VStack(spacing: 0) {
            Form {
                Section("Query") {
                    TextField("What are you looking for?", text: $searchController.query, onCommit: run)
                    Picker("Strategy", selection: $searchController.strategy) {
                        ForEach(RetrievalStrategy.allCases) { strategy in
                            Text(strategy.displayName).tag(strategy)
                        }
                    }
                    .pickerStyle(.segmented)
                    Toggle("Rerank with cross-encoder", isOn: $searchController.rerank)
                    Toggle("Diversify with MMR", isOn: $searchController.mmr)
                    Stepper("Top k: \(searchController.topK)", value: $searchController.topK, in: 1...50)
                    TextField("File type (optional, e.g. pdf)", text: $searchController.fileType)
                    HStack {
                        Spacer()
                        Button("Search") { run() }
                            .buttonStyle(.borderedProminent)
                            .disabled(searchController.query.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                                || searchController.isLoading)
                    }
                }
            }
            .formStyle(.grouped)
            .frame(maxHeight: 300)

            Divider()

            results
        }
        .navigationTitle("Search")
    }

    private func run() {
        Task {
            await searchController.runSearch(baseURL: settings.baseURL)
        }
    }

    @ViewBuilder
    private var results: some View {
        if searchController.isLoading {
            VStack(spacing: 8) {
                ProgressView()
                Text("Searching…")
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else if let error = searchController.errorMessage {
            VStack(spacing: 8) {
                Text(error)
                    .foregroundStyle(.red)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else if searchController.results.isEmpty {
            VStack(spacing: 8) {
                Text("No results yet")
                    .font(.title3.bold())
                Text("Run a search to see the ranked chunks, with the strategy and reranking you picked.")
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            VStack(alignment: .leading, spacing: 0) {
                if !searchController.statsSummary.isEmpty {
                    Text(searchController.statsSummary)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .padding(.horizontal)
                        .padding(.vertical, 6)
                }
                List(searchController.results) { result in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text("#\(result.rank)")
                                .font(.caption.bold())
                                .foregroundStyle(.secondary)
                            Text(result.source)
                                .font(.callout.bold())
                                .lineLimit(1)
                            Spacer()
                            Text(String(format: "%.3f", result.score))
                                .font(.caption.monospaced())
                                .foregroundStyle(.secondary)
                        }
                        Text(result.text)
                            .font(.callout)
                            .foregroundStyle(.secondary)
                            .lineLimit(6)
                    }
                    .padding(.vertical, 4)
                }
                .listStyle(.plain)
            }
        }
    }
}
