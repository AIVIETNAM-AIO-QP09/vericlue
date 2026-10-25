import Foundation
import XCTest
@testable import VeriClue

// Every URLSession in the API tests uses this protocol. Unscripted URLs fail closed:
// they can never fall through to DNS, sockets or URLSession.shared.
final class MockURLProtocol: URLProtocol, @unchecked Sendable {
    private final class WeakServer: @unchecked Sendable {
        nonisolated(unsafe) weak var value: MockServer?
        nonisolated init(_ value: MockServer) { self.value = value }
    }
    nonisolated private static let lock = NSLock()
    nonisolated(unsafe) private static var servers: [String: WeakServer] = [:]

    nonisolated static func register(_ server: MockServer, host: String) {
        lock.lock(); defer { lock.unlock() }
        servers[host] = WeakServer(server)
    }
    nonisolated static func unregister(host: String) {
        lock.lock(); defer { lock.unlock() }
        servers.removeValue(forKey: host)
    }
    nonisolated override class func canInit(with request: URLRequest) -> Bool { true }
    nonisolated override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    nonisolated override func startLoading() {
        Self.lock.lock()
        let server = Self.servers[request.url?.host ?? ""]?.value
        Self.lock.unlock()
        guard let server else {
            client?.urlProtocol(self, didFailWithError: URLError(.unsupportedURL))
            return
        }
        var captured = request
        if captured.httpBody == nil, let stream = captured.httpBodyStream {
            stream.open()
            defer { stream.close() }
            var bytes = Data()
            var buffer = [UInt8](repeating: 0, count: 4096)
            while stream.hasBytesAvailable {
                let count = stream.read(&buffer, maxLength: buffer.count)
                if count <= 0 { break }
                bytes.append(contentsOf: buffer.prefix(count))
            }
            captured.httpBody = bytes
        }
        let reply = server.take(captured)
        switch reply {
        case .failure(let error): client?.urlProtocol(self, didFailWithError: error)
        case .response(let status, let data):
            guard let url = request.url, let response = HTTPURLResponse(url: url, statusCode: status,
                httpVersion: nil, headerFields: ["Content-Type": "application/json"]) else { return }
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        }
    }
    nonisolated override func stopLoading() {}
}

final class MockServer: @unchecked Sendable {
    enum Reply: @unchecked Sendable {
        case response(Int, Data)
        case failure(URLError)
    }
    nonisolated let host = UUID().uuidString.lowercased() + ".invalid"
    nonisolated private let lock = NSLock()
    nonisolated(unsafe) private var replies: [Reply] = []
    nonisolated(unsafe) private var requests: [URLRequest] = []
    nonisolated(unsafe) private var unexpected = 0

    init() { MockURLProtocol.register(self, host: host) }
    deinit { MockURLProtocol.unregister(host: host) }

    func api() -> SessionApi {
        let config = SessionApi.configuration()
        config.protocolClasses = [MockURLProtocol.self]
        return SessionApi(baseURL: URL(string: "https://" + host + "/")!, session: URLSession(configuration: config))
    }
    nonisolated func enqueue(_ body: String, status: Int = 200) { enqueue(Data(body.utf8), status: status) }
    nonisolated func enqueue(_ body: Data, status: Int = 200) {
        lock.lock(); defer { lock.unlock() }
        replies.append(.response(status, body))
    }
    nonisolated func drop() {
        lock.lock(); defer { lock.unlock() }
        replies.append(.failure(URLError(.networkConnectionLost)))
    }
    nonisolated func error(_ status: Int, _ code: String) {
        enqueue("{\"error_code\":\"" + code + "\",\"message\":\"internal diagnostic\"}", status: status)
    }
    nonisolated func take(_ request: URLRequest) -> Reply {
        lock.lock(); defer { lock.unlock() }
        requests.append(request)
        guard !replies.isEmpty else {
            unexpected += 1
            return .failure(URLError(.resourceUnavailable))
        }
        return replies.removeFirst()
    }
    nonisolated var captured: [URLRequest] {
        lock.lock(); defer { lock.unlock() }
        return requests
    }
    nonisolated var unexpectedRequests: Int {
        lock.lock(); defer { lock.unlock() }
        return unexpected
    }
    nonisolated var remainingReplies: Int {
        lock.lock(); defer { lock.unlock() }
        return replies.count
    }
}

final class ContractFixtureBundle: NSObject {}

@MainActor
enum Fixtures {
    static func data(_ name: String) throws -> Data {
        let url = try XCTUnwrap(Bundle(for: ContractFixtureBundle.self).url(forResource: name, withExtension: "json"))
        return try Data(contentsOf: url)
    }
    static func session(dynamic: Bool = false) throws -> Data {
        try data(dynamic ? "session.CreateSessionResponse.dynamic" : "session.CreateSessionResponse")
    }
    static func challenge(id: String = "ch_next") throws -> String {
        let model = try SessionJSON.decoder().decode(CreateSessionResponse.self, from: session()).challenge
        let next = Challenge(challengeId: id, colorSequence: model.colorSequence)
        return String(decoding: try SessionJSON.encoder().encode(next), as: UTF8.self)
    }
    static let mediaAck = "{\"step\":\"media\",\"received\":true}"
    static let signalsAck = "{\"step\":\"signals\",\"received\":true}"
    static let pass = "{\"status\":\"pass\"}"
}
