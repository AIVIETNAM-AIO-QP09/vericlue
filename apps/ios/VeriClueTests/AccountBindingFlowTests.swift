import Foundation
import Testing
@testable import VeriClue

actor TestAccountSigner: MediaSigner {
    private(set) var messages: [Data] = []
    private var failing = false
    func failSigning() { failing = true }
    func publicKeySPKI() async throws -> String { "synthetic-public-spki" }
    func sign(_ message: Data) async throws -> String {
        if failing { throw ProofError.signing }
        messages.append(message)
        return "synthetic-signature"
    }
}

actor TestAccountKeys: AccountKeys {
    let signer = TestAccountSigner()
    let memory: MemoryReceiptDataStore
    private(set) var available: Set<String> = []
    private(set) var opened: [(String, Bool)] = []
    private(set) var deleted: [String] = []
    private(set) var bindingAtDelete: Data?
    private var deleteFails = false
    init(memory: MemoryReceiptDataStore) { self.memory = memory }
    func add(_ alias: String) { available.insert(alias) }
    func failDelete() { deleteFails = true }
    func exists(_ alias: String) async throws -> Bool { available.contains(alias) }
    func open(_ alias: String, create: Bool) async throws -> any MediaSigner {
        if !create && !available.contains(alias) { throw ProofError.unavailableKey }
        if create { available.insert(alias) }
        opened.append((alias, create))
        return signer
    }
    func delete(_ alias: String, lease: OperationLease) async throws {
        if deleteFails { throw ProofError.signing }
        try lease.perform {
            bindingAtDelete = memory.stored
            deleted.append(alias); available.remove(alias)
        }
    }
}

@MainActor
struct AccountBindingFlowTests {
    private let oldAlias = "vericlue.media.synthetic-old"
    private var receipt: AccountReceipt { ReceiptFixtures.value }

    @Test func bindingIsAtomicAndReceiptOnlyFormatCannotAcquireAnAlias() async throws {
        let memory = MemoryReceiptDataStore(), store = AccountBindingStore(backend: memory)
        memory.seed(try ReceiptFixtures.data)
        #expect(try await store.load() == nil)
        #expect(memory.stored == nil)
        let binding = StoredAccount(receipt: receipt, keyAlias: oldAlias)
        try await store.save(binding, lease: OperationLease())
        #expect(try await store.load() == binding)
        let bytes = try #require(memory.stored)
        let object = try #require(try JSONSerialization.jsonObject(with: bytes) as? [String: Any])
        #expect(Set(object.keys) == ["receipt", "key_alias"])
        memory.fail(on: "write")
        await #expect(throws: AccountStoreError.self) {
            try await store.save(StoredAccount(receipt: receipt, keyAlias: "vericlue.media.new"), lease: OperationLease())
        }
        #expect(memory.stored == bytes)
        memory.fail(on: nil)
        let cancelled = OperationLease(); cancelled.invalidate()
        await #expect(throws: CancellationError.self) { try await store.save(binding, lease: cancelled) }
        #expect(memory.stored == bytes)
    }

    @Test func authFallbackAndMissingKeyNeverGenerateReplacement() async throws {
        let memory = MemoryReceiptDataStore(), store = AccountBindingStore(backend: memory)
        let keys = TestAccountKeys(memory: memory), coordinator = AccountFlow(store: store, keys: keys)
        for purpose: Purpose in [.reauth, .recovery] {
            let unsigned = try await coordinator.begin(purpose, signingEnabled: false)
            #expect(unsigned.purpose == .onboarding && unsigned.route == .terms && unsigned.keyAlias == nil)
        }
        let unbound = try await coordinator.begin(.reauth, signingEnabled: true)
        #expect(unbound.purpose == .onboarding && unbound.route == .terms)
        try await store.save(StoredAccount(receipt: receipt, keyAlias: oldAlias), lease: OperationLease())
        let opensBeforeMissing = await keys.opened.count
        let missing = try await coordinator.begin(.reauth, signingEnabled: true)
        #expect(missing.route == .recoveryRequired && missing.signer == nil)
        #expect(await keys.opened.count == opensBeforeMissing)
        await keys.add(oldAlias)
        let found = try await coordinator.begin(.reauth, signingEnabled: true)
        #expect(found.route == .phone && found.receipt == receipt && found.keyAlias == oldAlias)
        let last = try #require(await keys.opened.last)
        #expect(last.0 == oldAlias && last.1 == false)
    }

    @Test func recoveryKeepsOldKeyOnSaveFailureAndDeletesOnlyAfterDurableWrite() async throws {
        let memory = MemoryReceiptDataStore(), store = AccountBindingStore(backend: memory)
        let keys = TestAccountKeys(memory: memory), coordinator = AccountFlow(store: store, keys: keys)
        let previous = StoredAccount(receipt: receipt, keyAlias: oldAlias)
        try await store.save(previous, lease: OperationLease()); await keys.add(oldAlias)
        let entry = try await coordinator.begin(.recovery, signingEnabled: true)
        #expect(entry.keyAlias != oldAlias && entry.receipt == receipt)
        let updated = AccountReceipt(accountId: receipt.accountId, deviceId: "dev_" + String(repeating: "c", count: 32), expiresAt: receipt.expiresAt)
        memory.fail(on: "write")
        #expect(try await coordinator.persist(updated, entry: entry, lease: OperationLease()) == .storage)
        #expect(await keys.deleted.isEmpty)
        #expect(try await store.load() == previous)
        memory.fail(on: nil)
        #expect(try await coordinator.persist(receipt, entry: entry, lease: OperationLease()) == .contextMismatch)
        #expect(try await coordinator.persist(updated, entry: entry, lease: OperationLease()) == .saved)
        #expect(await keys.deleted == [oldAlias])
        let stored = try #require(try await store.load())
        #expect(stored.receipt == updated && stored.keyAlias == entry.keyAlias)
        #expect(await keys.bindingAtDelete == memory.stored)
    }

    private func wait(_ count: Int, _ server: MockServer) async throws {
        for _ in 0..<200 {
            if server.captured.count >= count { return }
            try await Task.sleep(for: .milliseconds(10))
        }
        Issue.record("Synthetic request barrier timed out")
        throw URLError(.timedOut)
    }

    private func context(_ purpose: Purpose = .onboarding) -> (LiveFlow, MockServer, TestAccountSigner, MemoryReceiptDataStore) {
        let server = MockServer(), signer = TestAccountSigner(), memory = MemoryReceiptDataStore()
        let coordinator = AccountFlow(store: AccountBindingStore(backend: memory), keys: TestAccountKeys(memory: memory))
        let entry = AccountEntry(purpose: purpose, receipt: purpose == .reauth ? receipt : nil,
            keyAlias: "vericlue.media.synthetic-live", signer: signer, route: purpose == .onboarding ? .terms : .phone)
        return (LiveFlow(api: server.api(), accountEntry: entry, accountFlow: coordinator), server, signer, memory)
    }

    private func sessionReply(_ request: URLRequest, purpose: Purpose, seed: String? = String(repeating: "f", count: 64)) throws -> String {
        let sent = try SessionJSON.decoder().decode(CreateSessionRequest.self, from: try #require(request.httpBody))
        var value = try SessionJSON.decoder().decode(CreateSessionResponse.self, from: Fixtures.session())
        value.nonce = sent.nonce; value.purpose = purpose.rawValue
        value.expiresAt = "2099-01-01T00:00:00Z"; value.challenge.expiresAt = value.expiresAt
        value.challenge.mediaNonce = seed
        if purpose == .reauth {
            let expiry = Int64(Date().timeIntervalSince1970 * 1000) + 30000
            let formatter = ISO8601DateFormatter(); formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            let fields: [String: Any] = ["version": "vericlue-device-auth-v1", "session_id": value.sessionId,
                "purpose": "reauth", "account_id": receipt.accountId, "device_id": receipt.deviceId,
                "nonce": sent.nonce, "server_nonce": String(repeating: "a", count: 64), "expires_at_ms": expiry]
            let data = try JSONSerialization.data(withJSONObject: fields, options: [.sortedKeys])
            value.deviceChallenge = DeviceChallenge(message: data.base64EncodedString(),
                expiresAt: formatter.string(from: Date(timeIntervalSince1970: Double(expiry) / 1000)))
        }
        return String(decoding: try SessionJSON.encoder().encode(value), as: UTF8.self)
    }

    private func start(_ live: LiveFlow, _ server: MockServer, purpose: Purpose = .onboarding) async throws {
        let gate = server.hold()
        let pending = Task { await live.createSession(purpose: purpose) }
        try await wait(1, server)
        gate.release(try sessionReply(server.captured[0], purpose: purpose))
        #expect(await pending.value == nil)
    }

    @Test func reauthSessionIsInvisibleUntilProofACKAnd409NeverPublishesIt() async throws {
        for accept in [true, false] {
            let (live, server, signer, _) = context(.reauth)
            let creation = server.hold(), proof = server.hold()
            let pending = Task { await live.createSession(purpose: .reauth) }
            try await wait(1, server)
            let request = try SessionJSON.decoder().decode(CreateSessionRequest.self, from: server.captured[0].httpBody!)
            #expect(request.accountId == receipt.accountId && request.deviceId == receipt.deviceId && request.devicePublicKeySpki == nil)
            creation.release(try sessionReply(server.captured[0], purpose: .reauth))
            try await wait(2, server)
            #expect(live.session == nil && live.token == nil)
            #expect(server.captured[1].url?.lastPathComponent == "device-proof")
            if accept { proof.release("{\"received\":true}") }
            else { proof.release("{\"error_code\":\"recovery_required\",\"message\":\"synthetic\"}", status: 409) }
            let error = await pending.value
            #expect(accept ? error == nil && live.session != nil : error == .conflict(code: "recovery_required") && live.session == nil)
            #expect(await signer.messages.count == 1)
        }
    }

    @Test func signedFaceRetrySkipsAcknowledgedMediaAndSignsExactPendingBytes() async throws {
        let (live, server, signer, _) = context()
        try await start(live, server)
        let jpeg = Data([1,2,3]), video = Data([4,5,6])
        live.frontalJpeg = jpeg
        server.enqueue(Fixtures.mediaAck); server.drop()
        #expect(await live.submitFace(video: video) == .fail(.network))
        #expect(live.mediaAcked && !live.signalsAcked)
        live.frontalJpeg = Data([9])
        server.enqueue(Fixtures.signalsAck); server.enqueue("{\"status\":\"review\"}")
        #expect(await live.submitFace(video: Data([9])) == .to(.review))
        #expect(server.captured.filter { $0.url?.lastPathComponent == "media" }.count == 1)
        #expect(server.captured.filter { $0.url?.lastPathComponent == "signals" }.count == 2)
        let messages = await signer.messages
        #expect(messages.count == 1)
        let message = try #require(messages.first)
        #expect(message == (try MediaProof.manifest(session: live.session!, challenge: live.challenge!, stage: "face",
            attemptID: live.challenge!.challengeId, files: ["image": try MediaProof.digest(name: "face.jpg", bytes: jpeg),
                "video": try MediaProof.digest(name: "face.mp4", bytes: video)])))
    }

    @Test func signingFailureOrMissingSeedCannotFallBackToUnsigned() async throws {
        let (live, server, signer, _) = context()
        try await start(live, server); await signer.failSigning()
        live.frontalJpeg = Data([1])
        #expect(await live.submitFace() == .fail(.server))
        #expect(server.captured.count == 1)
        let (other, second, _, _) = context()
        let gate = second.hold(), pending = Task { await other.createSession(purpose: .onboarding) }
        try await wait(1, second)
        gate.release(try sessionReply(second.captured[0], purpose: .onboarding, seed: nil))
        #expect(await pending.value == .badResponse && other.session == nil)
    }

    @Test func passWaitsForBindingButMissingReceiptDoesNotUndoPass() async throws {
        let (live, server, _, memory) = context()
        try await start(live, server); live.frontalJpeg = Data([1])
        server.enqueue(Fixtures.mediaAck); server.enqueue(Fixtures.signalsAck); server.enqueue(Fixtures.pass)
        let receiptGate = server.hold()
        let pending = Task { await live.submitFace() }
        try await wait(5, server)
        #expect(memory.writeCount == 0 && live.bindingOutcome == nil && live.hasVerifiedPass)
        receiptGate.release(try ReceiptFixtures.json)
        #expect(await pending.value == .to(.success))
        #expect(memory.writeCount == 1 && live.bindingOutcome == .saved)
        let (missing, another, _, untouched) = context()
        try await start(missing, another); missing.frontalJpeg = Data([1])
        another.enqueue(Fixtures.mediaAck); another.enqueue(Fixtures.signalsAck); another.enqueue(Fixtures.pass)
        another.error(409, "account_not_enrolled")
        #expect(await missing.submitFace() == .to(.success))
        #expect(missing.receiptIssue != nil && untouched.writeCount == 0)
    }

    @Test func abandonBeforeReceiptResponseCannotWriteOrReturnSuccess() async throws {
        let (live, server, _, memory) = context()
        try await start(live, server); live.frontalJpeg = Data([1])
        server.enqueue(Fixtures.mediaAck); server.enqueue(Fixtures.signalsAck); server.enqueue(Fixtures.pass)
        let gate = server.hold(), pending = Task { await live.submitFace() }
        try await wait(5, server)
        live.reset(); gate.release(try ReceiptFixtures.json)
        #expect(await pending.value == .fail(.network))
        #expect(memory.writeCount == 0 && live.session == nil)
    }

    @Test func voiceRetrySignsOriginalWAVVideoAndOffsetNotNewArguments() async throws {
        let (live, server, signer, _) = context()
        try await start(live, server); live.frontalJpeg = Data([1])
        server.enqueue(Fixtures.mediaAck); server.enqueue(Fixtures.signalsAck)
        server.enqueue("{\"status\":\"voice_challenge\",\"voice_prompt\":\"Câu tổng hợp\",\"voice_challenge_id\":\"vc_test\"}")
        #expect(await live.submitFace() == .to(.voice))
        let wav = Data([2,3]), video = Data([4,5])
        server.drop()
        #expect(await live.submitVoice(wav: wav, video: video, audioOffsetMs: 114) == .fail(.network))
        server.enqueue("{\"status\":\"review\"}")
        #expect(await live.submitVoice(wav: Data([9]), video: Data([9]), audioOffsetMs: 999) == .to(.review))
        let messages = await signer.messages
        #expect(messages.count == 3 && messages[1] == messages[2])
        let expected = try MediaProof.manifest(session: live.session!, challenge: live.challenge!, stage: "voice", attemptID: "vc_test",
            files: ["audio": try MediaProof.digest(name: "voice.wav", bytes: wav), "video": try MediaProof.digest(name: "voice.mp4", bytes: video)], audioOffsetMs: 114)
        #expect(messages[2] == expected)
        let requests = server.captured.filter { $0.url?.lastPathComponent == "voice" }
        #expect(requests.count == 2)
        for request in requests {
            let body = String(decoding: request.httpBody!, as: UTF8.self)
            #expect(body.contains("name=\"audio_offset_ms\"\r\n\r\n114"))
            #expect(body.contains("name=\"media_signature\"\r\n\r\nsynthetic-signature"))
        }
    }

    @Test func rotatedChallengeAndTokenAreUsedAndPurposeCannotBeChanged() async throws {
        let (live, server, signer, _) = context()
        try await start(live, server)
        #expect(await live.createSession(purpose: .recovery) == .badResponse)
        var challenge = try #require(live.challenge)
        challenge = Challenge(challengeId: "ch_rotated", colorSequence: challenge.colorSequence,
            expiresAt: "2099-01-01T00:00:00Z", mediaNonce: String(repeating: "e", count: 64))
        let refreshed = ChallengeResponse(token: "synthetic_rotated", expiresAt: "2099-01-01T00:00:00Z", challenge: challenge)
        server.enqueue(try SessionJSON.encoder().encode(refreshed))
        #expect(await live.prepareFace(purpose: .onboarding) == nil)
        live.frontalJpeg = Data([1])
        server.enqueue(Fixtures.mediaAck); server.enqueue(Fixtures.signalsAck); server.enqueue("{\"status\":\"review\"}")
        #expect(await live.submitFace() == .to(.review))
        let media = try #require(server.captured.first { $0.url?.lastPathComponent == "media" })
        #expect(media.value(forHTTPHeaderField: "Authorization") == "Bearer synthetic_rotated")
        let signed = try #require(await signer.messages.first)
        let fields = try #require(try JSONSerialization.jsonObject(with: signed) as? [String: Any])
        #expect(fields["challenge_id"] as? String == "ch_rotated")
        #expect(fields["nonce"] as? String == MediaProof.sha256(Data((String(repeating: "e", count: 64) + ":face:ch_rotated").utf8)))
    }

    @Test func bindingWriteFailureKeepsPassAndMetadataRetryDoesNotRepeatBiometrics() async throws {
        let (live, server, _, memory) = context()
        try await start(live, server); live.frontalJpeg = Data([1])
        memory.fail(on: "write")
        server.enqueue(Fixtures.mediaAck); server.enqueue(Fixtures.signalsAck); server.enqueue(Fixtures.pass)
        server.enqueue(try ReceiptFixtures.data)
        #expect(await live.submitFace() == .to(.success))
        #expect(live.bindingOutcome == .storage && memory.writeCount == 0)
        memory.fail(on: nil)
        #expect(await live.receiptAfterPass() == receipt)
        #expect(live.bindingOutcome == .saved && memory.writeCount == 1)
        #expect(server.captured.count == 5)
    }

    @Test func lateDeviceACKAfterResetCannotPublishSession() async throws {
        let (live, server, _, memory) = context(.reauth)
        let created = server.hold(), proof = server.hold()
        let pending = Task { await live.createSession(purpose: .reauth) }
        try await wait(1, server)
        created.release(try sessionReply(server.captured[0], purpose: .reauth))
        try await wait(2, server)
        live.reset(); proof.release("{\"received\":true}")
        #expect(await pending.value == .network)
        #expect(live.session == nil && live.challenge == nil && memory.writeCount == 0)
    }

    @Test func unauthorizedOrFalseDeviceACKNeverCreatesUsableSession() async throws {
        for unauthorized in [false, true] {
            let (live, server, _, _) = context(.reauth)
            let created = server.hold()
            if unauthorized { server.error(401, "invalid_token") }
            else { server.enqueue("{\"received\":false}") }
            let pending = Task { await live.createSession(purpose: .reauth) }
            try await wait(1, server)
            created.release(try sessionReply(server.captured[0], purpose: .reauth))
            #expect(await pending.value == (unauthorized ? .unauthorized : .badResponse))
            #expect(live.session == nil && live.token == nil)
        }
    }

    @Test func oldKeyCleanupFailureDoesNotRollBackNewBinding() async throws {
        let memory = MemoryReceiptDataStore(), store = AccountBindingStore(backend: memory)
        let keys = TestAccountKeys(memory: memory), coordinator = AccountFlow(store: store, keys: keys)
        try await store.save(StoredAccount(receipt: receipt, keyAlias: oldAlias), lease: OperationLease())
        await keys.add(oldAlias)
        let entry = try await coordinator.begin(.recovery, signingEnabled: true)
        let updated = AccountReceipt(accountId: receipt.accountId, deviceId: "dev_" + String(repeating: "d", count: 32), expiresAt: receipt.expiresAt)
        await keys.failDelete()
        #expect(try await coordinator.persist(updated, entry: entry, lease: OperationLease()) == .oldKeyCleanup)
        #expect(try await store.load()?.receipt == updated)
        #expect(await keys.available.contains(oldAlias))
    }

    @Test func recoveryCannotOverwriteAnotherAlreadyReplacedBinding() async throws {
        let memory = MemoryReceiptDataStore(), store = AccountBindingStore(backend: memory)
        let keys = TestAccountKeys(memory: memory), coordinator = AccountFlow(store: store, keys: keys)
        try await store.save(StoredAccount(receipt: receipt, keyAlias: oldAlias), lease: OperationLease())
        await keys.add(oldAlias)
        let first = try await coordinator.begin(.recovery, signingEnabled: true)
        let second = try await coordinator.begin(.recovery, signingEnabled: true)
        let next = AccountReceipt(accountId: receipt.accountId, deviceId: "dev_" + String(repeating: "c", count: 32), expiresAt: receipt.expiresAt)
        #expect(try await coordinator.persist(next, entry: first, lease: OperationLease()) == .saved)
        #expect(try await coordinator.persist(next, entry: second, lease: OperationLease()) == .storage)
        #expect(try await store.load()?.keyAlias == first.keyAlias)
        #expect(await keys.deleted == [oldAlias])
    }
}
