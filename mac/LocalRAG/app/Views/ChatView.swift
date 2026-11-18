import SwiftUI

/// Chat with the documents: ask a question, get an answer with its
/// sources (citations) underneath.
struct ChatView: View {
    let sessionId: UUID?

    @EnvironmentObject private var settings: SettingsStore
    @EnvironmentObject private var chatController: ChatController

    @State private var input = ""

    private var session: ChatSession? {
        guard let sessionId else { return nil }
        return chatController.sessions.first { $0.id == sessionId }
    }

    private var messages: [ChatMessage] {
        session?.messages ?? []
    }

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 14) {
                        if messages.isEmpty {
                            emptyState
                        }
                        ForEach(messages) { message in
                            MessageRow(message: message)
                                .id(message.id)
                        }
                        if chatController.isLoading {
                            HStack(spacing: 8) {
                                ProgressView()
                                    .controlSize(.small)
                                Text("Thinking…")
                                    .foregroundStyle(.secondary)
                            }
                            .id("loading")
                        }
                    }
                    .padding()
                }
                .onChange(of: messages.count) { _, _ in
                    scrollToBottom(proxy)
                }
                .onChange(of: chatController.isLoading) { _, _ in
                    scrollToBottom(proxy)
                }
            }

            Divider()

            VStack(spacing: 8) {
                if let error = chatController.errorMessage {
                    Text(error)
                        .font(.callout)
                        .foregroundStyle(.red)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                HStack(spacing: 8) {
                    TextField("Ask about your documents…", text: $input, onCommit: send)
                        .textFieldStyle(.roundedBorder)
                    Button("Send") { send() }
                        .buttonStyle(.borderedProminent)
                        .disabled(sendDisabled)
                }
            }
            .padding()
        }
        .navigationTitle(session?.title ?? "New chat")
    }

    private var emptyState: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Ask about your documents")
                .font(.title2.bold())
            Text("Answers come from the files in the service's data/documents/ folder, with the passages they were built from listed underneath.")
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 24)
    }

    private var sendDisabled: Bool {
        input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            || chatController.isLoading
    }

    private func send() {
        let text = input
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        input = ""
        Task {
            await chatController.send(
                question: text, sessionId: sessionId, baseURL: settings.baseURL)
        }
    }

    private func scrollToBottom(_ proxy: ScrollViewProxy) {
        let target = chatController.isLoading ? "loading" : messages.last?.id
        if let target {
            withAnimation {
                proxy.scrollTo(target, anchor: .bottom)
            }
        }
    }
}

/// One message bubble. Assistant messages show their sources in a
/// collapsible section.
struct MessageRow: View {
    let message: ChatMessage

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                if message.role == .user {
                    Spacer()
                }
                Text(message.text)
                    .textSelection(.enabled)
                    .padding(10)
                    .background(message.role == .user ? Color.accentColor.opacity(0.15) : Color.secondary.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: 10))
                if message.role == .assistant {
                    Spacer()
                }
            }
            if message.role == .assistant, let sources = message.sources, !sources.isEmpty {
                DisclosureGroup("Sources (\(sources.count))") {
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(sources) { source in
                            VStack(alignment: .leading, spacing: 2) {
                                HStack {
                                    Text(source.source)
                                        .font(.callout.bold())
                                        .lineLimit(1)
                                    Spacer()
                                    Text(String(format: "%.2f", source.score))
                                        .font(.caption.monospaced())
                                        .foregroundStyle(.secondary)
                                }
                                Text(source.text)
                                    .font(.callout)
                                    .foregroundStyle(.secondary)
                                    .lineLimit(6)
                            }
                            .padding(8)
                            .background(Color.secondary.opacity(0.08))
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                        }
                    }
                    .padding(.top, 4)
                }
                .font(.callout)
            }
        }
    }
}
