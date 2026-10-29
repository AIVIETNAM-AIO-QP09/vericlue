import Foundation
import Testing
@testable import VeriClue

@MainActor
struct CaptureRecoveryTests {
    private func waitForRequests(_ count: Int, server: MockServer) async throws {
        for _ in 0..<200 {
            if server.captured.count >= count { return }
            try await Task.sleep(for: .milliseconds(10))
        }
        Issue.record("Mock request did not reach the barrier")
        throw URLError(.timedOut)
    }

    private func live(_ server: MockServer) async throws -> LiveFlow {
        let flow = LiveFlow(api: server.api())
        server.enqueue(try Fixtures.session(dynamic: true))
        #expect(await flow.createSession(purpose: .onboarding) == nil)
        flow.frontalJpeg = Data([1, 2, 3])
        return flow
    }

    private func refresh(_ id: String, token: String = "synthetic_rotated_not_a_credential") throws -> String {
        let session = try SessionJSON.decoder().decode(CreateSessionResponse.self, from: Fixtures.session(dynamic: true))
        var challenge = session.challenge
        challenge = Challenge(challengeId: id, colorSequence: challenge.colorSequence,
            baselineMs: challenge.baselineMs, captureAtMs: challenge.captureAtMs,
            expiresAt: challenge.expiresAt, dynamic: challenge.dynamic)
        return String(decoding: try SessionJSON.encoder().encode(ChallengeResponse(token: token,
            expiresAt: session.expiresAt, challenge: challenge)), as: UTF8.self)
    }

    @Test func backgroundPolicyRestartsCaptureButDoesNotDiscardNetworkRetry() {
        for stage in [FaceCaptureFlow.Stage.preparing, .framing, .recording, .finishing, .awaitingVoice] {
            #expect(stage.restartsOnInterruption)
        }
        #expect(!FaceCaptureFlow.Stage.uploading.restartsOnInterruption)
        #expect(!FaceCaptureFlow.Stage.completed.restartsOnInterruption)
        #expect(VoiceCaptureFlow.Stage.recording.restartsOnInterruption)
        #expect(!VoiceCaptureFlow.Stage.uploading.restartsOnInterruption)
        for route in [Route.faceReady, .framing, .holdStill, .turnHead, .voice, .voiceAgain, .uploading, .checking] {
            #expect(FlowRules.confirmsCaptureExit(route))
        }
        #expect(!FlowRules.confirmsCaptureExit(.phone))
        #expect(!FlowRules.confirmsCaptureExit(.bankStart))
        #expect(FlowRules.checkedByServer(voiceChecked: false) == ["Khuôn mặt"])
        #expect(FlowRules.checkedByServer(voiceChecked: true) == ["Khuôn mặt", "Giọng nói"])
    }

    @Test func interruptedVoiceRequiresFreshFaceAndClearsAllPendingBytes() async throws {
        let server = MockServer()
        let flow = try await live(server)
        let captures = CaptureFlows()
        captures.face.configure(live: flow, purpose: .onboarding)
        captures.voice.configure(live: flow, screenID: UUID())
        captures.background(at: .voice)
        #expect(captures.voice.stage == .interrupted)
        #expect(captures.voice.destination == .interrupted)
        #expect(flow.requiresFreshChallenge)
        #expect(flow.frontalJpeg == nil && flow.pendingWav == nil && flow.pendingFaceVideo == nil)
        #expect(!captures.face.camera.running && !captures.face.camera.recording)
        server.enqueue(try refresh("ch_after_background"))
        #expect(await flow.prepareFace() == nil)
        #expect(server.captured.last?.url?.lastPathComponent == "challenge")
        #expect(flow.challenge?.challengeId == "ch_after_background" && !flow.requiresFreshChallenge)
        captures.leaveFlow(live: flow)
    }

    @Test func interruptionDuringChallengeCannotStartCameraFromLateResponse() async throws {
        let server = MockServer()
        let flow = try await live(server)
        let face = FaceCaptureFlow()
        face.configure(live: flow, purpose: .onboarding)
        let gate = server.hold()
        let pending = Task { await face.prepare() }
        try await waitForRequests(2, server: server)
        #expect(face.stage == .preparing)
        face.interrupt()
        gate.release(try refresh("ch_late"))
        await pending.value
        #expect(face.stage == .interrupted && face.destination == .interrupted)
        #expect(!face.camera.running && !face.camera.recording && flow.requiresFreshChallenge)
        #expect(flow.challenge?.challengeId != "ch_late")
    }

    @Test func oldOperationCannotReleaseNewBusyLeaseOrRotateItsToken() async throws {
        let server = MockServer()
        let flow = try await live(server)
        let oldGate = server.hold()
        let old = Task { await flow.prepareFace() }
        try await waitForRequests(2, server: server)
        flow.abandonFaceAttempt()
        let newGate = server.hold()
        let new = Task { await flow.prepareFace() }
        try await waitForRequests(3, server: server)
        oldGate.release(try refresh("ch_stale", token: "stale_synthetic_value"))
        #expect(await old.value == .network)
        #expect(await flow.createSession() == .busy)
        newGate.release(try refresh("ch_current"))
        #expect(await new.value == nil)
        #expect(flow.challenge?.challengeId == "ch_current")
        #expect(flow.token == "synthetic_rotated_not_a_credential")
    }

    @Test(arguments: [0, 1, 2])
    func abandonedUploadNeverAcknowledgesOrSucceeds(_ step: Int) async throws {
        let server = MockServer()
        let flow = try await live(server)
        for body in [Fixtures.mediaAck, Fixtures.signalsAck].prefix(step) { server.enqueue(body) }
        let gate = server.hold()
        var released = 0
        let pending = Task { await flow.submitFace(video: Data([7]), onMediaAcked: { released += 1 }) }
        try await waitForRequests(step + 2, server: server)
        let releasedBefore = released
        flow.abandonFaceAttempt()
        gate.release(step == 0 ? Fixtures.mediaAck : step == 1 ? Fixtures.signalsAck : Fixtures.pass)
        #expect(await pending.value == .fail(.network))
        #expect(released == releasedBefore)
        #expect(!flow.mediaAcked && !flow.signalsAcked && !flow.voiceChecked)
        #expect(flow.frontalJpeg == nil && flow.pendingFaceVideo == nil && flow.requiresFreshChallenge)
    }

    @Test(arguments: [0, 1, 2])
    func transportRetryDoesNotRefreshOrResendReceivedSteps(_ step: Int) async throws {
        let server = MockServer()
        let flow = try await live(server)
        let bodies = [Fixtures.mediaAck, Fixtures.signalsAck, Fixtures.pass]
        for body in bodies.prefix(step) { server.enqueue(body) }
        server.drop()
        #expect(await flow.submitFace(video: Data([7])) == .fail(.network))
        #expect(flow.mediaAcked == (step > 0) && flow.signalsAcked == (step > 1))
        #expect(!flow.requiresFreshChallenge)
        for body in bodies.dropFirst(step) { server.enqueue(body) }
        #expect(await flow.submitFace() == .to(.success))
        let paths = server.captured.dropFirst().map { $0.url!.lastPathComponent }
        let expected = ["media", "signals", "finalize"]
        #expect(paths == Array(expected.prefix(step + 1)) + Array(expected.dropFirst(step)))
        #expect(!paths.contains("challenge"))
    }

    @Test func cancelledVoiceCannotInvokeReceiptCleanupOrSuccess() async throws {
        let server = MockServer()
        let flow = try await live(server)
        server.enqueue(Fixtures.mediaAck); server.enqueue(Fixtures.signalsAck)
        server.enqueue("{\"status\":\"voice_challenge\",\"voice_prompt\":\"Câu tổng hợp\",\"voice_challenge_id\":\"vc_synthetic\"}")
        #expect(await flow.submitFace() == .to(.voice))
        let gate = server.hold()
        var accepted = 0
        let pending = Task {
            await flow.submitVoice(wav: Data([1, 2]), video: Data([3]), audioOffsetMs: 100,
                                   onAccepted: { accepted += 1 })
        }
        try await waitForRequests(5, server: server)
        flow.abandonFaceAttempt()
        gate.release(Fixtures.pass)
        #expect(await pending.value == .fail(.network))
        #expect(accepted == 0 && !flow.voiceChecked)
        #expect(flow.pendingWav == nil && flow.pendingVoiceVideo == nil && flow.voicePrompt == nil)
        #expect(await flow.submitVoice(wav: Data([9])) == .fail(.conflict(code: "challenge_expired")))
    }

    @Test func resetCannotBeRepopulatedByLateSessionReply() async throws {
        let server = MockServer()
        let flow = LiveFlow(api: server.api())
        let gate = server.hold()
        let pending = Task { await flow.createSession(purpose: .onboarding) }
        try await waitForRequests(1, server: server)
        flow.reset()
        gate.release(String(decoding: try Fixtures.session(dynamic: true), as: UTF8.self))
        #expect(await pending.value == .network)
        #expect(flow.session == nil && flow.token == nil && flow.challenge == nil)
    }

    @Test func expiryClearsCaptureAndRoutesToSessionErrorWithoutNetwork() async throws {
        let server = MockServer()
        let flow = LiveFlow(api: server.api())
        var response = try SessionJSON.decoder().decode(CreateSessionResponse.self, from: Fixtures.session(dynamic: true))
        response.expiresAt = "2000-01-01T00:00:00Z"
        server.enqueue(try SessionJSON.encoder().encode(response))
        #expect(await flow.createSession(purpose: .onboarding) == nil)
        let captures = CaptureFlows()
        captures.face.configure(live: flow, purpose: .onboarding)
        captures.monitorExpiry(live: flow)
        for _ in 0..<100 where captures.expiryDestination == nil { try await Task.sleep(for: .milliseconds(10)) }
        #expect(captures.expiryDestination == .errorSession)
        #expect(flow.requiresFreshChallenge && !flow.mediaAcked && flow.pendingWav == nil)
        #expect(server.captured.count == 1 && !captures.face.camera.recording)
        captures.leaveFlow(live: flow)
    }

    @Test func expiryParsesFractionalAndWholeSecondsAtExactDeadline() {
        let deadline = Date(timeIntervalSince1970: 0)
        #expect(FlowRules.sessionExpired("1970-01-01T00:00:00Z", now: deadline))
        #expect(!FlowRules.sessionExpired("1970-01-01T00:00:00.500Z", now: deadline))
        #expect(!FlowRules.sessionExpired("invalid", now: deadline))
    }
}
