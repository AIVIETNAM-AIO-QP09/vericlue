#if DEBUG
import CryptoKit
import Foundation
import Testing
@testable import VeriClue

nonisolated private struct ProbeTestSigner: MediaSigner {
    let key: P256.Signing.PrivateKey
    func publicKeySPKI() async throws -> String { key.publicKey.derRepresentation.base64EncodedString() }
    func sign(_ message: Data) async throws -> String { try key.signature(for: message).derRepresentation.base64EncodedString() }
}

private actor ProbeTestKeys: AccountKeys {
    private var keys: [String: P256.Signing.PrivateKey] = [:]
    private(set) var creations = 0
    private(set) var deletions = 0
    func exists(_ alias: String) async throws -> Bool { keys[alias] != nil }
    func open(_ alias: String, create: Bool) async throws -> any MediaSigner {
        if let key = keys[alias] { return ProbeTestSigner(key: key) }
        guard create else { throw ProofError.unavailableKey }
        let key = P256.Signing.PrivateKey()
        keys[alias] = key; creations += 1
        return ProbeTestSigner(key: key)
    }
    func delete(_ alias: String, lease: OperationLease) async throws {
        try lease.perform { keys.removeValue(forKey: alias); deletions += 1 }
    }
}

@MainActor
struct DeviceKeyProbeTests {
    @Test func probeReopensSameKeyAndNeverRecreatesMissingKey() async throws {
        let backend = MemoryReceiptDataStore(), keys = ProbeTestKeys()
        let first = DeviceKeyProbe(backend: backend, keys: keys)
        try await first.create()
        let saved = try #require(backend.stored)
        let reopened = DeviceKeyProbe(backend: backend, keys: keys)
        try await reopened.reopenAndVerify()
        let creations = await keys.creations
        #expect(backend.stored == saved && creations == 1)
        try await reopened.removeKeyButKeepRecord()
        #expect(backend.stored == saved)
        await #expect(throws: ProofError.self) { try await reopened.reopenAndVerify() }
        #expect(await keys.creations == 1)
        try await reopened.clear()
        #expect(backend.stored == nil)
    }

    @Test func probeCannotOpenOrDeleteAnAccountAliasFromTamperedMetadata() async throws {
        let backend = MemoryReceiptDataStore(), keys = ProbeTestKeys()
        backend.seed(try JSONEncoder().encode(DeviceKeyProbeRecord(alias: "vericlue.media.live-account", publicKey: "unused")))
        let probe = DeviceKeyProbe(backend: backend, keys: keys)
        await #expect(throws: DeviceKeyProbeError.self) { try await probe.clear() }
        await #expect(throws: DeviceKeyProbeError.self) { try await probe.reopenAndVerify() }
        let deletions = await keys.deletions, creations = await keys.creations
        #expect(deletions == 0 && creations == 0)
        #expect(backend.stored != nil)
        #expect(!DeviceKeyProbe.owns("vericlue.media.live-account"))
        #expect(!DeviceKeyProbe.owns(DeviceKeyProbe.prefix + "../x"))
        #expect(DeviceKeyProbe.owns(DeviceKeyProbe.prefix + UUID().uuidString))
    }
}
#endif
