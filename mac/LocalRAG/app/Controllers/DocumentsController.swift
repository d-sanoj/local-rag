import Foundation

/// Owns the indexed-documents list: loading it, triggering a folder
/// sync, and deleting documents from the index.
@MainActor
final class DocumentsController: ObservableObject {
    @Published private(set) var documents: [DocumentInfo] = []
    @Published private(set) var isLoading = false
    @Published private(set) var isSyncing = false
    @Published var lastSync: SyncResult?
    @Published var errorMessage: String?

    func load(baseURL: URL) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let client = LocalRAGClient(baseURL: baseURL)
            documents = try await client.listDocuments()
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription
                ?? error.localizedDescription
        }
    }

    func sync(baseURL: URL) async {
        isSyncing = true
        errorMessage = nil
        defer { isSyncing = false }
        do {
            let client = LocalRAGClient(baseURL: baseURL)
            lastSync = try await client.syncDocuments()
            documents = try await client.listDocuments()
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription
                ?? error.localizedDescription
        }
    }

    func delete(_ document: DocumentInfo, baseURL: URL) async {
        errorMessage = nil
        do {
            let client = LocalRAGClient(baseURL: baseURL)
            try await client.deleteDocument(id: document.id)
            documents.removeAll { $0.id == document.id }
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription
                ?? error.localizedDescription
        }
    }
}
