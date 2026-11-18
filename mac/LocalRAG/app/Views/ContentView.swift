import SwiftUI

enum SidebarSelection: Hashable {
    case chat(UUID?)
    case search
    case documents
    case stats
}

struct ContentView: View {
    @EnvironmentObject private var settings: SettingsStore
    @EnvironmentObject private var appController: AppController
    @EnvironmentObject private var chatController: ChatController

    @State private var selection: SidebarSelection? = .chat(nil)
    @State private var showingSettings = false

    var body: some View {
        NavigationSplitView {
            sidebar
        } detail: {
            detail
        }
        .task {
            await appController.checkHealth()
        }
        .onChange(of: settings.baseURLString) { _, _ in
            Task { await appController.checkHealth() }
        }
        .onChange(of: chatController.currentSessionId) { _, newId in
            if let newId {
                selection = .chat(newId)
            }
        }
        .sheet(isPresented: $showingSettings) {
            SettingsView()
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    Task { await appController.checkHealth() }
                } label: {
                    Label("Refresh connection", systemImage: "arrow.clockwise")
                }
                .help("Check the service again")
            }
            ToolbarItem(placement: .primaryAction) {
                Button {
                    showingSettings = true
                } label: {
                    Label("Settings", systemImage: "gearshape")
                }
                .help("Service address")
            }
        }
    }

    // MARK: - Sidebar

    private var sidebar: some View {
        List(selection: $selection) {
            Section("Chat") {
                Button {
                    chatController.newChat()
                    selection = .chat(chatController.currentSessionId)
                } label: {
                    Label("New chat", systemImage: "plus.message")
                }
                .buttonStyle(.plain)

                ForEach(chatController.sessions) { session in
                    NavigationLink(value: SidebarSelection.chat(session.id)) {
                        Label {
                            Text(session.title)
                                .lineLimit(1)
                        } icon: {
                            Image(systemName: "message")
                        }
                    }
                    .contextMenu {
                        Button("Delete", role: .destructive) {
                            chatController.deleteSession(session.id)
                        }
                    }
                }
            }

            Section("Library") {
                NavigationLink(value: SidebarSelection.search) {
                    Label("Search", systemImage: "magnifyingglass")
                }
                NavigationLink(value: SidebarSelection.documents) {
                    Label("Documents", systemImage: "folder")
                }
                NavigationLink(value: SidebarSelection.stats) {
                    Label("Stats", systemImage: "chart.bar")
                }
            }

            Section("Service") {
                HealthStatusRow()
            }
        }
        .navigationTitle("Local RAG")
    }

    // MARK: - Detail

    @ViewBuilder
    private var detail: some View {
        if appController.connectionState == .unreachable {
            ConnectionView()
        } else {
            switch selection ?? .chat(nil) {
            case .chat(let sessionId):
                ChatView(sessionId: sessionId)
            case .search:
                SearchView()
            case .documents:
                DocumentsView()
            case .stats:
                StatsView()
            }
        }
    }
}

/// The connection status row at the bottom of the sidebar.
struct HealthStatusRow: View {
    @EnvironmentObject private var appController: AppController

    var body: some View {
        HStack(spacing: 8) {
            Circle()
                .fill(dotColor)
                .frame(width: 9, height: 9)
            VStack(alignment: .leading, spacing: 1) {
                Text(statusText)
                    .font(.subheadline)
                if let health = appController.health {
                    Text("\(health.documents) documents · \(health.chunks) chunks")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                } else if let error = appController.lastError {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }
            Spacer()
            if appController.connectionState == .checking {
                ProgressView()
                    .controlSize(.small)
            }
        }
    }

    private var dotColor: Color {
        switch appController.connectionState {
        case .connected: return .green
        case .degraded: return .orange
        case .checking: return .gray
        case .unreachable: return .red
        }
    }

    private var statusText: String {
        switch appController.connectionState {
        case .connected: return "Connected"
        case .degraded: return "Connected — degraded"
        case .checking: return "Checking…"
        case .unreachable: return "Service unreachable"
        }
    }
}

/// The service-address settings sheet.
struct SettingsView: View {
    @EnvironmentObject private var settings: SettingsStore
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Service address")
                .font(.title2.bold())
            Text("The address of the local-rag service. The default is the service as started by ./run.sh in the local-rag repo.")
                .foregroundStyle(.secondary)
            TextField("http://localhost:8000", text: $settings.baseURLString)
                .textFieldStyle(.roundedBorder)
            HStack {
                Button("Reset to default") {
                    settings.resetToDefault()
                }
                Spacer()
                Button("Done") { dismiss() }
                    .buttonStyle(.borderedProminent)
            }
            Spacer()
        }
        .padding(24)
        .frame(width: 420, height: 220)
    }
}
