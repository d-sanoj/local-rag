import Foundation

/// One message in a chat session. Assistant messages carry the sources
/// (citations) the answer was built from.
struct ChatMessage: Identifiable, Codable {
    enum Role: String, Codable {
        case user
        case assistant
    }

    let id: UUID
    let role: Role
    let text: String
    let sources: [Source]?
    let createdAt: Date

    init(id: UUID = UUID(), role: Role, text: String, sources: [Source]? = nil, createdAt: Date = Date()) {
        self.id = id
        self.role = role
        self.text = text
        self.sources = sources
        self.createdAt = createdAt
    }
}

/// One chat conversation, persisted locally as JSON.
struct ChatSession: Identifiable, Codable {
    let id: UUID
    var title: String
    var messages: [ChatMessage]
    let createdAt: Date

    init(id: UUID = UUID(), title: String = "New chat", messages: [ChatMessage] = [], createdAt: Date = Date()) {
        self.id = id
        self.title = title
        self.messages = messages
        self.createdAt = createdAt
    }
}
