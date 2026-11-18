import Foundation

/// Owns chat sessions: sending questions to the service, keeping the
/// local history, and persisting it.
@MainActor
final class ChatController: ObservableObject {
    @Published private(set) var sessions: [ChatSession] = []
    @Published var currentSessionId: UUID?
    @Published private(set) var isLoading = false
    @Published var errorMessage: String?

    private let store = ChatHistoryStore()

    init() {
        sessions = store.load()
        currentSessionId = sessions.first?.id
    }

    var currentSession: ChatSession? {
        guard let currentSessionId else { return nil }
        return sessions.first { $0.id == currentSessionId }
    }

    func newChat() {
        let session = ChatSession()
        sessions.insert(session, at: 0)
        currentSessionId = session.id
        save()
    }

    func selectSession(_ id: UUID) {
        currentSessionId = id
    }

    func deleteSession(_ id: UUID) {
        sessions.removeAll { $0.id == id }
        if currentSessionId == id {
            currentSessionId = sessions.first?.id
        }
        save()
    }

    /// Sends a question. Creates a session first when `sessionId` is nil
    /// or does not match a known session.
    func send(question: String, sessionId: UUID?, baseURL: URL) async {
        let trimmed = question.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !isLoading else { return }

        let targetId: UUID
        if let sessionId, sessions.contains(where: { $0.id == sessionId }) {
            targetId = sessionId
        } else {
            let session = ChatSession()
            sessions.insert(session, at: 0)
            targetId = session.id
            currentSessionId = targetId
        }
        guard let index = sessions.firstIndex(where: { $0.id == targetId }) else { return }

        if sessions[index].title == "New chat" {
            sessions[index].title = String(trimmed.prefix(40))
        }
        sessions[index].messages.append(
            ChatMessage(role: .user, text: trimmed))
        save()

        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        do {
            let client = LocalRAGClient(baseURL: baseURL)
            let response = try await client.query(
                QueryRequest(question: trimmed))
            guard let currentIndex = sessions.firstIndex(where: { $0.id == targetId }) else { return }
            sessions[currentIndex].messages.append(
                ChatMessage(role: .assistant, text: response.answer, sources: response.sources))
            save()
        } catch {
            errorMessage = (error as? LocalizedError)?.errorDescription
                ?? error.localizedDescription
        }
    }

    private func save() {
        store.save(sessions)
    }
}
