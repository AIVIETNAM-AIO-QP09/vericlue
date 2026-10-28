import Foundation
import Testing
@testable import VeriClue

@MainActor
struct ReceiptFlowTests {
    private func flow(_ server: MockServer, memory: MemoryReceiptDataStore, purpose: Purpose = .onboarding) async throws -> LiveFlow {
        let live = LiveFlow(api: server.api(), accountStore: AccountStore(backend: memory))
        var session = try SessionJSON.decoder().decode(CreateSessionResponse.self, from: Fixtures.session(dynamic: true))
        session.purpose = purpose.rawValue
        server.enqueue(try SessionJSON.encoder().encode(session))
        #expect(await live.createSession(purpose: purpose) == nil)
        live.frontalJpeg = Data([1, 2])
        return live
    }

    private func finalize(_ server: MockServer, _ live: LiveFlow, status: String = "pass") async {
        server.enqueue(Fixtures.mediaAck); server.enqueue(Fixtures.signalsAck)
        server.enqueue("{\"status\":\"\(status)\"}")
        #expect(await live.submitFace() == .to(status == "pass" ? .success : .review))
    }

    @Test func finalizePassFetchesAndSavesOnlyWhenReceiptStepIsRequested() async throws {
        let server = MockServer(), memory = MemoryReceiptDataStore()
        let live = try await flow(server, memory: memory)
        await finalize(server, live)
        #expect(server.captured.count == 4 && memory.writeCount == 0)
        server.enqueue(try ReceiptFixtures.data)
        #expect(await live.receiptAfterPass() == ReceiptFixtures.value)
        #expect(server.captured.last?.httpMethod == "GET")
        #expect(server.captured.last?.url?.lastPathComponent == "account")
        #expect(memory.writeCount == 1 && live.receiptIssue == nil)
        #expect(await live.receiptAfterPass() == ReceiptFixtures.value)
        #expect(server.captured.count == 5 && memory.writeCount == 1)
    }

    @Test(arguments: ["network", "401", "404", "503", "malformed", "expired"])
    func receiptFailureDoesNotRerunBiometricsOrBecomeAReceipt(_ failure: String) async throws {
        let server = MockServer(), memory = MemoryReceiptDataStore()
        let live = try await flow(server, memory: memory)
        await finalize(server, live)
        switch failure {
        case "network": server.drop()
        case "malformed": server.enqueue("{}")
        case "expired":
            let old = AccountReceipt(accountId: ReceiptFixtures.value.accountId,
                deviceId: ReceiptFixtures.value.deviceId, expiresAt: "2000-01-01T00:00:00Z")
            server.enqueue(try SessionJSON.encoder().encode(old))
        default: server.error(Int(failure)!, "synthetic_receipt_error")
        }
        #expect(await live.receiptAfterPass() == nil)
        #expect(live.receiptIssue != nil && live.accountReceipt == nil && memory.stored == nil)
        server.enqueue(try ReceiptFixtures.data)
        #expect(await live.receiptAfterPass() == ReceiptFixtures.value)
        #expect(server.captured.dropFirst(4).allSatisfy { $0.httpMethod == "GET" && $0.url?.lastPathComponent == "account" })
        #expect(server.captured.count == 6 && server.unexpectedRequests == 0)
    }

    @Test func voicePassReceiptAvoidsGETAndIsSaved() async throws {
        let server = MockServer(), memory = MemoryReceiptDataStore()
        let live = try await flow(server, memory: memory, purpose: .recovery)
        server.enqueue(Fixtures.mediaAck); server.enqueue(Fixtures.signalsAck)
        server.enqueue("{\"status\":\"voice_challenge\",\"voice_prompt\":\"Câu tổng hợp\",\"voice_challenge_id\":\"vc_synthetic\"}")
        #expect(await live.submitFace() == .to(.voice))
        server.enqueue("{\"status\":\"pass\",\"account\":\(try ReceiptFixtures.json)}")
        #expect(await live.submitVoice(wav: Data([7])) == .to(.success))
        #expect(live.accountReceipt == ReceiptFixtures.value && live.voiceChecked)
        #expect(await live.receiptAfterPass() == ReceiptFixtures.value)
        #expect(server.captured.count == 5 && memory.writeCount == 1)
    }

    @Test func malformedVoiceReceiptStillPassesAndCanBeFetchedSeparately() async throws {
        let server = MockServer(), memory = MemoryReceiptDataStore()
        let live = try await flow(server, memory: memory)
        server.enqueue(Fixtures.mediaAck); server.enqueue(Fixtures.signalsAck)
        server.enqueue("{\"status\":\"voice_challenge\",\"voice_prompt\":\"Câu tổng hợp\",\"voice_challenge_id\":\"vc_synthetic\"}")
        #expect(await live.submitFace() == .to(.voice))
        server.enqueue("{\"status\":\"pass\",\"account\":{}}")
        #expect(await live.submitVoice(wav: Data([1])) == .to(.success))
        #expect(live.accountReceipt == nil)
        server.enqueue(try ReceiptFixtures.data)
        #expect(await live.receiptAfterPass() == ReceiptFixtures.value)
        #expect(server.captured.map { $0.url!.lastPathComponent } == ["sessions", "media", "signals", "finalize", "voice", "account"])
    }

    @Test func saveFailureRetriesStorageWithoutFetchingOrSubmittingAgain() async throws {
        let server = MockServer(), memory = MemoryReceiptDataStore()
        let live = try await flow(server, memory: memory)
        await finalize(server, live)
        server.enqueue(try ReceiptFixtures.data)
        memory.fail(on: "write")
        #expect(await live.receiptAfterPass() == nil && live.receiptIssue == .storage)
        #expect(live.accountReceipt == ReceiptFixtures.value && memory.stored == nil)
        memory.fail(on: nil)
        #expect(await live.receiptAfterPass() == ReceiptFixtures.value)
        #expect(server.captured.count == 5 && memory.writeCount == 1 && live.receiptIssue == nil)
    }

    @Test func receiptCannotBeFetchedBeforePassAfterReviewOrForReauth() async throws {
        let server = MockServer(), memory = MemoryReceiptDataStore()
        let live = try await flow(server, memory: memory)
        #expect(await live.receiptAfterPass() == nil && server.captured.count == 1)
        await finalize(server, live, status: "review")
        #expect(await live.receiptAfterPass() == nil && server.captured.count == 4)
        let reauthServer = MockServer()
        let reauth = try await flow(reauthServer, memory: memory, purpose: .reauth)
        await finalize(reauthServer, reauth)
        #expect(await reauth.receiptAfterPass() == nil && reauthServer.captured.count == 4)
        #expect(memory.writeCount == 0)
    }

    @Test func reviewVoiceReceiptIsIgnoredAndCannotOverwriteSavedAccount() async throws {
        let server = MockServer(), memory = MemoryReceiptDataStore()
        let original = try ReceiptFixtures.data
        memory.seed(original)
        let live = try await flow(server, memory: memory)
        server.enqueue(Fixtures.mediaAck); server.enqueue(Fixtures.signalsAck)
        server.enqueue("{\"status\":\"voice_challenge\",\"voice_prompt\":\"Câu tổng hợp\",\"voice_challenge_id\":\"vc_synthetic\"}")
        #expect(await live.submitFace() == .to(.voice))
        server.enqueue("{\"status\":\"review\",\"account\":\(try ReceiptFixtures.json)}")
        #expect(await live.submitVoice(wav: Data([1])) == .to(.review))
        #expect(await live.receiptAfterPass() == nil && live.accountReceipt == nil)
        #expect(server.captured.count == 5 && memory.writeCount == 0 && memory.stored == original)
    }

    @Test func abandonedReceiptReplyCannotPersistOrRepopulateResetSession() async throws {
        let server = MockServer(), memory = MemoryReceiptDataStore()
        let live = try await flow(server, memory: memory)
        await finalize(server, live)
        let gate = server.hold()
        let pending = Task { await live.receiptAfterPass() }
        for _ in 0..<200 where server.captured.count < 5 { try await Task.sleep(for: .milliseconds(10)) }
        #expect(server.captured.count == 5)
        // The lease rejects a second receipt request too.
        #expect(await live.receiptAfterPass() == nil && server.captured.count == 5)
        live.reset()
        gate.release(try ReceiptFixtures.json)
        #expect(await pending.value == nil)
        #expect(live.session == nil && live.accountReceipt == nil && live.receiptIssue == nil)
        #expect(memory.writeCount == 0 && server.unexpectedRequests == 0)
    }

    @Test func receiptGETUsesRotatedTokenAndResetKeepsOnlyPersistedReceipt() async throws {
        let server = MockServer(), memory = MemoryReceiptDataStore()
        let live = try await flow(server, memory: memory)
        let challenge = try Fixtures.challenge(id: "ch_rotated")
        server.enqueue("{\"token\":\"synthetic_rotated\",\"expires_at\":\"2100-01-01T00:00:00Z\",\"challenge\":\(challenge)}")
        #expect(await live.prepareFace() == nil)
        live.frontalJpeg = Data([1])
        await finalize(server, live)
        server.enqueue(try ReceiptFixtures.data)
        #expect(await live.receiptAfterPass() == ReceiptFixtures.value)
        #expect(server.captured.last?.value(forHTTPHeaderField: "Authorization") == "Bearer synthetic_rotated")
        let persisted = try #require(memory.stored)
        #expect(try SessionJSON.decoder().decode(AccountReceipt.self, from: persisted) == ReceiptFixtures.value)
        live.reset()
        #expect(live.token == nil && live.accountReceipt == nil)
        #expect(memory.stored == persisted)
        #expect(await live.receiptAfterPass() == nil && server.captured.count == 6)
    }

    @Test func collectorOutlivesTriggerWithoutDuplicateGETAndResetCancelsIt() async throws {
        let server = MockServer(), memory = MemoryReceiptDataStore()
        let live = try await flow(server, memory: memory)
        await finalize(server, live)
        let first = server.hold()
        // The screen trigger returns immediately; its task is not the GET owner.
        let trigger = Task { live.collectReceiptAfterPass() }
        await trigger.value
        for _ in 0..<200 where server.captured.count < 5 { try await Task.sleep(for: .milliseconds(10)) }
        #expect(server.captured.count == 5)
        live.collectReceiptAfterPass()
        #expect(server.captured.count == 5)
        first.release(try ReceiptFixtures.json)
        for _ in 0..<200 where memory.writeCount == 0 { try await Task.sleep(for: .milliseconds(10)) }
        #expect(memory.writeCount == 1 && live.accountReceipt == ReceiptFixtures.value)
        live.reset()

        let secondServer = MockServer()
        let next = try await flow(secondServer, memory: memory)
        await finalize(secondServer, next)
        let late = secondServer.hold()
        next.collectReceiptAfterPass()
        for _ in 0..<200 where secondServer.captured.count < 5 { try await Task.sleep(for: .milliseconds(10)) }
        #expect(secondServer.captured.count == 5)
        next.reset()
        late.release(try ReceiptFixtures.json)
        #expect(await next.receiptAfterPass() == nil && next.accountReceipt == nil)
        #expect(memory.writeCount == 1)
    }
}
