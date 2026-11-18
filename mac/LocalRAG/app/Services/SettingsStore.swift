import Foundation

/// The service's base URL, persisted in UserDefaults. Default is the
/// local-rag service as started by `./run.sh`.
final class SettingsStore: ObservableObject {
    @Published var baseURLString: String {
        didSet {
            UserDefaults.standard.set(baseURLString, forKey: Self.baseURLKey)
        }
    }

    private static let baseURLKey = "apiBaseURL"
    static let defaultBaseURLString = "http://localhost:8000"

    init() {
        self.baseURLString = UserDefaults.standard.string(forKey: Self.baseURLKey)
            ?? Self.defaultBaseURLString
    }

    var baseURL: URL {
        let trimmed = baseURLString.trimmingCharacters(in: .whitespacesAndNewlines)
        return URL(string: trimmed) ?? URL(string: Self.defaultBaseURLString)!
    }

    func resetToDefault() {
        baseURLString = Self.defaultBaseURLString
    }
}
