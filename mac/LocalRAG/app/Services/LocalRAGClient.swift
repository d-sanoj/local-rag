import Foundation

/// Errors surfaced to the user. The `detail` string comes from FastAPI's
/// `{"detail": ...}` error body when the server returns one.
enum APIError: LocalizedError {
    case invalidURL
    case network(URLError)
    case http(status: Int, detail: String)
    case decoding(Error)
    case unknown(Error)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "The service URL is not valid."
        case .network(let error):
            return error.localizedDescription
        case .http(_, let detail):
            return detail
        case .decoding:
            return "The service returned data this app could not understand."
        case .unknown(let error):
            return error.localizedDescription
        }
    }
}

/// Thin HTTP client for the local-rag service. Every call is a plain
/// JSON request/response — the service does not stream.
struct LocalRAGClient {
    let baseURL: URL
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let string = try container.decode(String.self)
            let withFraction = ISO8601DateFormatter()
            withFraction.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = withFraction.date(from: string) { return date }
            let plain = ISO8601DateFormatter()
            plain.formatOptions = [.withInternetDateTime]
            if let date = plain.date(from: string) { return date }
            throw DecodingError.dataCorruptedError(
                in: container, debugDescription: "Invalid ISO 8601 date: \(string)")
        }
        self.decoder = decoder

        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .iso8601
        self.encoder = encoder
    }

    // MARK: - Health / stats

    func fetchHealth() async throws -> HealthResponse {
        try await get("health")
    }

    func fetchStats() async throws -> StatsResponse {
        try await get("api/v1/stats")
    }

    // MARK: - Query / search

    func query(_ request: QueryRequest) async throws -> QueryResponse {
        try await post("api/v1/query", body: request)
    }

    func search(_ request: SearchRequest) async throws -> SearchResponse {
        try await post("api/v1/search", body: request)
    }

    // MARK: - Documents

    func listDocuments() async throws -> [DocumentInfo] {
        try await get("api/v1/documents")
    }

    func syncDocuments() async throws -> SyncResult {
        try await post("api/v1/documents/sync", body: EmptyBody())
    }

    func deleteDocument(id: String) async throws {
        try await delete("api/v1/documents/\(id)")
    }

    // MARK: - Transport

    private struct EmptyBody: Encodable {}

    /// FastAPI's error body: `{"detail": "message"}` (or a list for
    /// validation errors). Returns the message, or a fallback.
    private func detail(from data: Data?) -> String {
        guard let data,
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let detail = json["detail"] else {
            return "The service returned an error."
        }
        if let message = detail as? String { return message }
        if let items = detail as? [[String: Any]] {
            return items.compactMap { $0["msg"] as? String }.joined(separator: "; ")
        }
        return "The service returned an error."
    }

    private func url(for path: String) -> URL {
        // appendingPathComponent (not relative-URL resolution) so a base
        // URL with or without a trailing slash always joins correctly.
        var url = baseURL
        for component in path.split(separator: "/") {
            url.appendPathComponent(String(component))
        }
        return url
    }

    private func get<T: Decodable>(_ path: String) async throws -> T {
        let request = URLRequest(url: url(for: path))
        return try await perform(request)
    }

    private func post<Body: Encodable, T: Decodable>(_ path: String, body: Body) async throws -> T {
        var request = URLRequest(url: url(for: path))
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        do {
            request.httpBody = try encoder.encode(body)
        } catch {
            throw APIError.decoding(error)
        }
        return try await perform(request)
    }

    private func delete(_ path: String) async throws {
        var request = URLRequest(url: url(for: path))
        request.httpMethod = "DELETE"
        let (_, response) = try await send(request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.unknown(URLError(.badServerResponse))
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.http(status: httpResponse.statusCode, detail: "Delete failed.")
        }
    }

    private func send(_ request: URLRequest) async throws -> (Data, URLResponse) {
        do {
            return try await session.data(for: request)
        } catch let error as URLError {
            throw APIError.network(error)
        } catch {
            throw APIError.unknown(error)
        }
    }

    private func perform<T: Decodable>(_ request: URLRequest) async throws -> T {
        let (data, response) = try await send(request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.unknown(URLError(.badServerResponse))
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.http(status: httpResponse.statusCode, detail: detail(from: data))
        }
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw APIError.decoding(error)
        }
    }
}
