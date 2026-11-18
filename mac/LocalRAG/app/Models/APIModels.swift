import Foundation

/// API models for the local-rag service.
///
/// Field names match the server's Pydantic schemas exactly (the client's
/// JSONDecoder uses `.convertFromSnakeCase`, so Swift properties are
/// camelCase here and snake_case on the wire).

enum RetrievalStrategy: String, Codable, CaseIterable, Identifiable {
    case dense
    case sparse
    case hybrid

    var id: String { rawValue }
    var displayName: String { rawValue.capitalized }
}

/// A JSON value of unknown shape (used for `retrieval_stats`, whose keys
/// vary by strategy: candidates, reranked, mmr, returned, ...).
enum JSONValue: Codable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case array([JSONValue])
    case object([String: JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else if let value = try? container.decode([String: JSONValue].self) {
            self = .object(value)
        } else {
            throw DecodingError.dataCorruptedError(
                in: container, debugDescription: "Unsupported JSON value")
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value): try container.encode(value)
        case .number(let value): try container.encode(value)
        case .bool(let value): try container.encode(value)
        case .array(let value): try container.encode(value)
        case .object(let value): try container.encode(value)
        case .null: try container.encodeNil()
        }
    }

    /// Short human-readable rendering, e.g. `12` or `true`.
    var displayString: String {
        switch self {
        case .string(let value): return value
        case .number(let value):
            return value.truncatingRemainder(dividingBy: 1) == 0
                ? String(Int(value)) : String(value)
        case .bool(let value): return value ? "yes" : "no"
        case .array(let value): return value.map(\.displayString).joined(separator: ", ")
        case .object(let value):
            return value.map { "\($0.key): \($0.value.displayString)" }
                .sorted().joined(separator: ", ")
        case .null: return "—"
        }
    }
}

struct Filters: Codable {
    var source: String?
    var fileType: String?
    var indexedAfter: Date?
    var indexedBefore: Date?

    init(source: String? = nil, fileType: String? = nil) {
        self.source = source
        self.fileType = fileType
    }
}

struct SearchRequest: Codable {
    var query: String
    var strategy: RetrievalStrategy = .hybrid
    var rerank: Bool = true
    var mmr: Bool = false
    var topK: Int = 5
    var filters: Filters? = nil
}

struct SearchResult: Codable, Identifiable {
    var chunkId: String
    var documentId: String
    var source: String
    var text: String
    var score: Double
    var rank: Int
    var metadata: [String: JSONValue]?

    var id: String { chunkId }
}

struct SearchResponse: Codable {
    var query: String
    var strategy: String
    var reranked: Bool
    var results: [SearchResult]
    var retrievalStats: [String: JSONValue]?

    /// One-line summary of the retrieval stats, e.g. `candidates: 20 · returned: 5`.
    var statsSummary: String {
        guard let retrievalStats, !retrievalStats.isEmpty else { return "" }
        return retrievalStats
            .sorted(by: { $0.key < $1.key })
            .map { "\($0.key): \($0.value.displayString)" }
            .joined(separator: " · ")
    }
}

struct QueryRequest: Codable {
    var question: String
    var strategy: RetrievalStrategy = .hybrid
    var rerank: Bool = true
    var mmr: Bool = false
    var topK: Int = 5
    var filters: Filters? = nil
}

struct Source: Codable, Identifiable {
    var rank: Int
    var source: String
    var chunkId: String
    var text: String
    var score: Double
    var metadata: [String: JSONValue]?

    var id: String { chunkId }
}

struct QueryResponse: Codable {
    var question: String
    var answer: String
    var sources: [Source]
    var retrievalStats: [String: JSONValue]?

    var statsSummary: String {
        guard let retrievalStats, !retrievalStats.isEmpty else { return "" }
        return retrievalStats
            .sorted(by: { $0.key < $1.key })
            .map { "\($0.key): \($0.value.displayString)" }
            .joined(separator: " · ")
    }
}

struct DocumentInfo: Codable, Identifiable {
    var id: String
    var path: String
    var fileType: String
    var chunkCount: Int
    var sha256: String
    var indexedAt: Date

    /// The file name without its folder, for display.
    var fileName: String {
        (path as NSString).lastPathComponent
    }
}

struct SyncResult: Codable {
    var added: [String] = []
    var updated: [String] = []
    var removed: [String] = []
    var skippedUnsupported: [String] = []
    var documents: Int = 0
    var chunks: Int = 0

    var summary: String {
        "added \(added.count) · updated \(updated.count) · removed \(removed.count) · \(documents) documents, \(chunks) chunks"
    }
}

struct StatsResponse: Codable {
    var documentsFolder: String
    var documents: Int
    var chunks: Int
    var vectorStoreDocuments: Int
    var bm25Documents: Int
    var vectorDbDir: String
}

struct HealthResponse: Codable {
    var status: String
    var llmAvailable: Bool
    var ollamaModel: String
    var embeddingProvider: String
    var embeddingModel: String
    var embeddingLoaded: Bool
    var rerankerProvider: String
    var rerankerModel: String
    var rerankerLoaded: Bool
    var documents: Int
    var chunks: Int
    var watcherRunning: Bool
    var syncStatus: String

    var isHealthy: Bool { status == "ok" }
}
