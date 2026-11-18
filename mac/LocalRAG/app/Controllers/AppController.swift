import Foundation

/// Owns the connection to the local-rag service: health checks, stats,
/// and the connection state the UI renders.
@MainActor
final class AppController: ObservableObject {
    enum ConnectionState: Equatable {
        case checking
        case connected
        case degraded
        case unreachable
    }

    @Published private(set) var health: HealthResponse?
    @Published private(set) var stats: StatsResponse?
    @Published private(set) var connectionState: ConnectionState = .checking
    @Published private(set) var lastError: String?

    private let settings: SettingsStore

    init(settings: SettingsStore) {
        self.settings = settings
    }

    /// One health check. Sets `connectionState` from the result.
    func checkHealth() async {
        connectionState = .checking
        do {
            let client = LocalRAGClient(baseURL: settings.baseURL)
            let health = try await client.fetchHealth()
            self.health = health
            lastError = nil
            connectionState = health.isHealthy ? .connected : .degraded
        } catch {
            health = nil
            lastError = (error as? LocalizedError)?.errorDescription
                ?? error.localizedDescription
            connectionState = .unreachable
        }
    }

    func fetchStats() async {
        do {
            let client = LocalRAGClient(baseURL: settings.baseURL)
            stats = try await client.fetchStats()
        } catch {
            // Stats are secondary; the health check already reports the
            // connection state. Keep the last good stats on failure.
            NSLog("LocalRAG: could not fetch stats: \(error)")
        }
    }
}
