import SwiftUI

/// Index statistics and model status.
struct StatsView: View {
    @EnvironmentObject private var settings: SettingsStore
    @EnvironmentObject private var appController: AppController

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                if let stats = appController.stats {
                    Section("Index") {
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 160), spacing: 12)], spacing: 12) {
                            StatCard(title: "Documents", value: "\(stats.documents)")
                            StatCard(title: "Chunks", value: "\(stats.chunks)")
                            StatCard(title: "Vector store", value: "\(stats.vectorStoreDocuments)")
                            StatCard(title: "BM25 docs", value: "\(stats.bm25Documents)")
                        }
                        VStack(alignment: .leading, spacing: 4) {
                            LabeledValue(label: "Documents folder", value: stats.documentsFolder)
                            LabeledValue(label: "Vector DB", value: stats.vectorDbDir)
                        }
                        .font(.callout)
                    }
                } else {
                    ProgressView("Loading stats…")
                }

                if let health = appController.health {
                    Section("Models") {
                        VStack(alignment: .leading, spacing: 6) {
                            ModelRow(name: "Embeddings", detail: "\(health.embeddingProvider) · \(health.embeddingModel)", loaded: health.embeddingLoaded)
                            ModelRow(name: "Reranker", detail: "\(health.rerankerProvider) · \(health.rerankerModel)", loaded: health.rerankerLoaded)
                            ModelRow(name: "LLM", detail: "Ollama · \(health.ollamaModel)", loaded: health.llmAvailable)
                        }
                    }
                    Section("Service") {
                        VStack(alignment: .leading, spacing: 6) {
                            LabeledValue(label: "Status", value: health.status)
                            LabeledValue(label: "Folder watcher", value: health.watcherRunning ? "running" : "stopped")
                            LabeledValue(label: "Sync", value: health.syncStatus)
                        }
                        .font(.callout)
                    }
                }
                Spacer()
            }
            .padding()
            .frame(maxWidth: 720, alignment: .leading)
        }
        .navigationTitle("Stats")
        .task {
            await appController.fetchStats()
        }
    }
}

struct StatCard: View {
    let title: String
    let value: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.callout)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.title2.bold())
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(Color.secondary.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 10))
    }
}

struct LabeledValue: View {
    let label: String
    let value: String

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(label)
                .foregroundStyle(.secondary)
                .frame(width: 130, alignment: .leading)
            Text(value)
                .textSelection(.enabled)
        }
    }
}

struct ModelRow: View {
    let name: String
    let detail: String
    let loaded: Bool

    var body: some View {
        HStack {
            Circle()
                .fill(loaded ? Color.green : Color.orange)
                .frame(width: 9, height: 9)
            Text(name)
                .font(.callout.bold())
                .frame(width: 90, alignment: .leading)
            Text(detail)
                .font(.callout)
                .foregroundStyle(.secondary)
            Spacer()
            Text(loaded ? "loaded" : "not loaded")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}
