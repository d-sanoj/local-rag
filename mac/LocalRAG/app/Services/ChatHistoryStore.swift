import Foundation

/// Persists chat sessions as JSON under
/// `~/Library/Application Support/LocalRAG/chat-history.json`.
struct ChatHistoryStore {
    private var directory: URL {
        FileManager.default
            .urls(for: .applicationSupportDirectory, in: .userDomainMask)
            .first!
            .appendingPathComponent("LocalRAG", isDirectory: true)
    }

    private var fileURL: URL {
        directory.appendingPathComponent("chat-history.json")
    }

    func load() -> [ChatSession] {
        guard let data = try? Data(contentsOf: fileURL) else { return [] }
        return (try? JSONDecoder().decode([ChatSession].self, from: data)) ?? []
    }

    func save(_ sessions: [ChatSession]) {
        do {
            try FileManager.default.createDirectory(
                at: directory, withIntermediateDirectories: true)
            let data = try JSONEncoder().encode(sessions)
            try data.write(to: fileURL, options: .atomic)
        } catch {
            // History is a convenience, never a reason to fail the app.
            NSLog("LocalRAG: could not save chat history: \(error)")
        }
    }
}
