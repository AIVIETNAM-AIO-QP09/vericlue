import Foundation
import Security
import Testing
@testable import VeriClue

// Synthetic, isolated test storage. No real Keychain or biometric data.
final class MemoryReceiptDataStore: ReceiptDataStore, @unchecked Sendable {
    nonisolated private let lock = NSLock()
    nonisolated(unsafe) private var bytes: Data?
    nonisolated(unsafe) private var failure: String?
    nonisolated(unsafe) private var writes = 0
    nonisolated(unsafe) private var deletions = 0

    nonisolated func fail(on operation: String?) { lock.lock(); failure = operation; lock.unlock() }
    nonisolated func seed(_ data: Data?) { lock.lock(); bytes = data; lock.unlock() }
    nonisolated var stored: Data? { lock.lock(); defer { lock.unlock() }; return bytes }
    nonisolated var writeCount: Int { lock.lock(); defer { lock.unlock() }; return writes }
    nonisolated var deleteCount: Int { lock.lock(); defer { lock.unlock() }; return deletions }

    nonisolated func read() throws -> Data? {
        lock.lock(); defer { lock.unlock() }
        if failure == "read" { throw AccountStoreError.keychain(errSecInteractionNotAllowed) }
        return bytes
    }
    nonisolated func write(_ data: Data) throws {
        lock.lock(); defer { lock.unlock() }
        if failure == "write" { throw AccountStoreError.keychain(errSecNotAvailable) }
        bytes = data; writes += 1
    }
    nonisolated func delete() throws {
        lock.lock(); defer { lock.unlock() }
        if failure == "delete" { throw AccountStoreError.keychain(errSecNotAvailable) }
        bytes = nil; deletions += 1
    }
}

@MainActor
enum ReceiptFixtures {
    static let value = AccountReceipt(accountId: "acct_" + String(repeating: "a", count: 32),
        deviceId: "dev_" + String(repeating: "b", count: 32), expiresAt: "2100-01-01T00:00:00Z")
    static var data: Data { get throws { try SessionJSON.encoder().encode(value) } }
    static var json: String { get throws { String(decoding: try data, as: UTF8.self) } }
}

@MainActor
struct AccountReceiptTests {
    @Test func receiptCodecMatchesPublishedReferenceAndPersistsOnlyThreeFields() async throws {
        let raw = try ReceiptFixtures.json.dropLast() + ",\"session_token\":\"synthetic_not_a_credential\"}"
        let decoded = try SessionJSON.decoder().decode(AccountReceipt.self, from: Data(raw.utf8))
        #expect(decoded == ReceiptFixtures.value)
        let memory = MemoryReceiptDataStore()
        let store = AccountStore(backend: memory)
        try await store.save(decoded)
        let bytes = try #require(memory.stored)
        let fields = try #require(JSONSerialization.jsonObject(with: bytes) as? [String: Any])
        #expect(Set(fields.keys) == ["account_id", "device_id", "expires_at"])
        #expect(try await store.load() == decoded)
    }

    @Test(arguments: ["{}", "{\"account_id\":\"acct_bad\",\"device_id\":\"dev_bad\",\"expires_at\":\"2100-01-01T00:00:00Z\"}"])
    func missingOrInvalidRequiredFieldsFail(_ json: String) {
        #expect(throws: DecodingError.self) { try SessionJSON.decoder().decode(AccountReceipt.self, from: Data(json.utf8)) }
    }

    @Test func identifierPatternsAndDatesAreValidated() throws {
        let good = ReceiptFixtures.value
        for bad in [
            AccountReceipt(accountId: good.accountId.uppercased(), deviceId: good.deviceId, expiresAt: good.expiresAt),
            AccountReceipt(accountId: good.accountId, deviceId: "dev_" + String(repeating: "z", count: 32), expiresAt: good.expiresAt),
            AccountReceipt(accountId: good.accountId, deviceId: good.deviceId, expiresAt: "not-a-date")
        ] {
            #expect(!bad.isWellFormed)
            let data = try SessionJSON.encoder().encode(bad)
            #expect(throws: DecodingError.self) { try SessionJSON.decoder().decode(AccountReceipt.self, from: data) }
        }
        let fractional = AccountReceipt(accountId: good.accountId, deviceId: good.deviceId, expiresAt: "1970-01-01T00:00:00.500Z")
        #expect(fractional.isUsable(at: Date(timeIntervalSince1970: 0)))
        #expect(!fractional.isUsable(at: Date(timeIntervalSince1970: 0.5)))
    }

    @Test func everyReceiptFieldIsRequired() throws {
        let object = try #require(JSONSerialization.jsonObject(with: ReceiptFixtures.data) as? [String: Any])
        for field in ["account_id", "device_id", "expires_at"] {
            var missing = object
            missing.removeValue(forKey: field)
            let data = try JSONSerialization.data(withJSONObject: missing)
            #expect(throws: DecodingError.self) { try SessionJSON.decoder().decode(AccountReceipt.self, from: data) }
        }
    }

    @Test func GETUsesCurrentBearerNoStoreAndNoRequestBody() async throws {
        let server = MockServer()
        server.enqueue(try ReceiptFixtures.data)
        #expect(try await server.api().accountReceipt(sessionId: "ses_synthetic", token: "synthetic_rotated").get() == ReceiptFixtures.value)
        let request = try #require(server.captured.first)
        #expect(request.httpMethod == "GET" && request.url?.path == "/v1/sessions/ses_synthetic/account")
        #expect(request.value(forHTTPHeaderField: "Authorization") == "Bearer synthetic_rotated")
        #expect(request.value(forHTTPHeaderField: "Cache-Control") == "no-store")
        #expect(request.httpBody == nil && request.value(forHTTPHeaderField: "Content-Type") == nil)
        #expect(server.unexpectedRequests == 0)
    }

    @Test func GETErrorsRemainErrorsWithoutSyntheticReceipt() async throws {
        let server = MockServer()
        let api = server.api()
        for (status, expected) in [(401, ApiError.unauthorized), (409, .conflict(code: "no_receipt")),
                                   (422, .badResponse), (503, .busy), (404, .badResponse)] {
            server.error(status, "no_receipt")
            #expect(await api.accountReceipt(sessionId: "ses_synthetic", token: "synthetic") == .failure(expected))
        }
        server.enqueue("{}")
        #expect(await api.accountReceipt(sessionId: "ses_synthetic", token: "synthetic") == .failure(.badResponse))
        server.drop()
        #expect(await api.accountReceipt(sessionId: "ses_synthetic", token: "synthetic") == .failure(.network))
        #expect(server.unexpectedRequests == 0)
    }

    @Test func absentOrMalformedVoiceReceiptDoesNotUndoPassButBadCoreJSONStillFails() throws {
        for json in ["{\"status\":\"pass\"}", "{\"status\":\"pass\",\"account\":{}}",
                     "{\"status\":\"pass\",\"account\":null}"] {
            let response = try SessionJSON.decoder().decode(VoiceResponse.self, from: Data(json.utf8))
            #expect(response.status == "pass" && response.account == nil)
        }
        #expect(throws: DecodingError.self) {
            try SessionJSON.decoder().decode(VoiceResponse.self, from: Data("{\"account\":{}}".utf8))
        }
    }

    @Test func loadDropsExpiredAndCorruptButNeverDeletesOnReadError() async throws {
        let memory = MemoryReceiptDataStore()
        let store = AccountStore(backend: memory)
        #expect(try await store.load() == nil)
        let original = try ReceiptFixtures.data
        memory.seed(original)
        let deadline = try #require(ReceiptFixtures.value.expirationDate)
        #expect(try await store.load(at: deadline) == nil)
        #expect(memory.stored == nil && memory.deleteCount == 1)
        memory.seed(Data("broken".utf8))
        #expect(try await store.load() == nil)
        #expect(memory.stored == nil && memory.deleteCount == 2)
        memory.seed(original)
        memory.fail(on: "read")
        do { _ = try await store.load(); Issue.record("Read failure must propagate") }
        catch { #expect(error as? AccountStoreError == .keychain(errSecInteractionNotAllowed)) }
        #expect(memory.stored == original && memory.deleteCount == 2)
    }

    @Test func failedSavePreservesOldReceiptAndClearIsExplicit() async throws {
        let memory = MemoryReceiptDataStore()
        let store = AccountStore(backend: memory)
        try await store.save(ReceiptFixtures.value)
        let original = try #require(memory.stored)
        memory.fail(on: "write")
        do { try await store.save(ReceiptFixtures.value); Issue.record("Write failure must propagate") }
        catch { #expect(error as? AccountStoreError == .keychain(errSecNotAvailable)) }
        #expect(memory.stored == original)
        memory.fail(on: nil)
        let expired = AccountReceipt(accountId: ReceiptFixtures.value.accountId,
            deviceId: ReceiptFixtures.value.deviceId, expiresAt: "2000-01-01T00:00:00Z")
        do { try await store.save(expired); Issue.record("Expired receipt cannot be saved") }
        catch { #expect(error as? AccountStoreError == .invalidReceipt) }
        #expect(memory.writeCount == 1)
        memory.fail(on: "delete")
        do { try await store.clear(); Issue.record("Delete failure must propagate") }
        catch { #expect(error as? AccountStoreError == .keychain(errSecNotAvailable)) }
        #expect(memory.stored == original)
        memory.fail(on: nil)
        try await store.clear()
        #expect(try await store.load() == nil && memory.deleteCount == 1)
    }
}
