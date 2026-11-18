import SwiftUI

/// The indexed-documents list: what is in the vector DB, a manual sync,
/// and per-document removal.
struct DocumentsView: View {
    @EnvironmentObject private var settings: SettingsStore
    @EnvironmentObject private var documentsController: DocumentsController

    @State private var documentToDelete: DocumentInfo?

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text("Files come from the service's data/documents/ folder. Add, edit, or delete files there — the watcher picks them up. Sync forces a re-scan now.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                Spacer()
                Button("Sync now") {
                    Task { await documentsController.sync(baseURL: settings.baseURL) }
                }
                .buttonStyle(.borderedProminent)
                .disabled(documentsController.isSyncing)
            }
            .padding()

            if let sync = documentsController.lastSync {
                Text(sync.summary)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal)
                    .padding(.bottom, 6)
            }

            if let error = documentsController.errorMessage {
                Text(error)
                    .font(.callout)
                    .foregroundStyle(.red)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal)
                    .padding(.bottom, 6)
            }

            if documentsController.isLoading && documentsController.documents.isEmpty {
                ProgressView("Loading documents…")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if documentsController.documents.isEmpty {
                VStack(spacing: 8) {
                    Text("No documents indexed")
                        .font(.title3.bold())
                    Text("Put files in data/documents/ and press Sync now — or wait for the watcher to pick them up.")
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List(documentsController.documents) { document in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(document.fileName)
                                .font(.callout.bold())
                                .lineLimit(1)
                            Text(document.path)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(1)
                        }
                        Spacer()
                        VStack(alignment: .trailing, spacing: 2) {
                            Text("\(document.chunkCount) chunks")
                                .font(.callout)
                            Text(document.fileType)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Text(document.indexedAt, style: .date)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        Button(role: .destructive) {
                            documentToDelete = document
                        } label: {
                            Image(systemName: "trash")
                        }
                        .buttonStyle(.borderless)
                        .help("Remove from the index")
                    }
                    .padding(.vertical, 4)
                }
                .listStyle(.plain)
            }
        }
        .navigationTitle("Documents")
        .task {
            await documentsController.load(baseURL: settings.baseURL)
        }
        .alert("Remove from the index?", isPresented: Binding(
            get: { documentToDelete != nil },
            set: { if !$0 { documentToDelete = nil } }
        )) {
            Button("Cancel", role: .cancel) { documentToDelete = nil }
            Button("Remove", role: .destructive) {
                if let document = documentToDelete {
                    documentToDelete = nil
                    Task { await documentsController.delete(document, baseURL: settings.baseURL) }
                }
            }
        } message: {
            if let document = documentToDelete {
                Text("“\(document.fileName)” and its \(document.chunkCount) chunks will be removed from the vector database. The file itself stays in data/documents/ — the watcher will re-index it unless you delete it there too.")
            }
        }
    }
}
