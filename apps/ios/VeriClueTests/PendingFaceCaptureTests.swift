import Foundation
import Testing
@testable import VeriClue

@MainActor
struct PendingFaceCaptureTests {
    private let fields = IdCardFields(fullName: "Người Dùng Mẫu", idNumber: "000000000001",
        dateOfBirth: "1995-01-01", sex: "Nam", address: "Địa chỉ mẫu")

    private func session() throws -> Data {
        var value = try SessionJSON.decoder().decode(CreateSessionResponse.self, from: Fixtures.session(dynamic: true))
        value.expiresAt = "2100-01-01T00:00:00Z"
        value.challenge.expiresAt = "2099-01-01T00:00:00Z"
        return try SessionJSON.encoder().encode(value)
    }

    private func identity(_ server: MockServer) async throws -> IdentityFlow {
        let identity = IdentityFlow(api: server.api())
        identity.begin(purpose: .onboarding, scenario: "genuine")
        identity.phone = "0912345678"
        server.enqueue(try session())
        server.enqueue("{\"expires_at\":\"2100-01-01T00:00:00Z\",\"attempts_left\":5}")
        #expect(await identity.sendOTP() == .otp)
        identity.code = "654321"
        server.enqueue("{\"status\":\"pass\",\"attempts_left\":5}")
        #expect(await identity.verifyOTP() == .idFront)
        let qr = "000000000001|000000001|Người Dùng Mẫu|01011995|Nam|Địa chỉ mẫu|01012021"
        identity.acceptPhoto(IDCardPhoto(jpeg: Data([1]), sharpness: 100, glareFraction: 0, qr: qr), isBack: false)
        identity.acceptPhoto(IDCardPhoto(jpeg: Data([2]), sharpness: 100, glareFraction: 0, qr: nil), isBack: true)
        server.enqueue(try SessionJSON.encoder().encode(IdCardResponse(status: "ok", fields: fields)))
        #expect(await identity.uploadCard() == .faceReady)
        return identity
    }

    private func retain(_ face: FaceCaptureFlow, live: LiveFlow, purpose: Purpose = .onboarding,
                        screenID: UUID? = nil) throws -> URL {
        face.configure(live: live, purpose: purpose, screenID: screenID)
        let url = try CaptureFileStore.makeVideoURL(voice: false)
        // Transport fixture only, not a claim that these bytes form a valid MP4.
        try Data("synthetic transport fixture".utf8).write(to: url)
        let current = try #require(live.session), challenge = try #require(live.challenge)
        let binding = try #require(FaceAttemptBinding(session: current, challenge: challenge))
        face.retainCompletedCapture(PendingFaceCapture(videoURL: url,
            evidence: FaceEvidence(jpeg: Data([1, 2]), frameTimes: [FrameTime(mediaTime: 0)], regionMeans: [],
                duplicateRatio: 0, aeAwbLocked: true, frontalAtMs: 0, firstHostSeconds: 0, clockDeltaMs: 0, diagnostics: [:]),
            probe: CamProbe(apiTamperFlags: [], deviceLabel: "synthetic", duplicateFrameRatio: 0),
            quality: [:], events: [], binding: binding))
        return url
    }

    @Test func completedCaptureDoesNotUploadOrDisappearBeforeConfirmation() async throws {
        let server = MockServer(), captures = CaptureFlows()
        let identity = try await identity(server)
        let live = try #require(identity.liveFlow)
        let screenID = UUID()
        let url = try retain(captures.face, live: live, screenID: screenID)
        defer { captures.leaveFlow(live: live) }
        let count = server.captured.count
        #expect(captures.face.stage == .awaitingConfirmation && captures.face.destination == .confirm)
        captures.face.leaveFaceScreen(screenID)
        captures.background(at: .confirm)
        await captures.face.submit()
        #expect(server.captured.count == count && !live.mediaAcked && !live.idCardConfirmed)
        #expect(captures.face.hasPendingCapture && FileManager.default.fileExists(atPath: url.path))
        #expect(!captures.face.camera.running && !captures.face.camera.recording)
    }

    @Test func confirmNetworkRetryKeepsDraftAndFileAndSignalsRetryDoesNotResendMedia() async throws {
        let server = MockServer(), captures = CaptureFlows()
        let identity = try await identity(server), live = try #require(identity.liveFlow)
        let url = try retain(captures.face, live: live)
        defer { captures.leaveFlow(live: live) }
        identity.draftValues[0] = "Tên Mẫu Đã Sửa"
        identity.draftValues[2] = "02/01/1995"
        identity.draftValues[1] = "999999999999"
        server.drop()
        #expect(await captures.confirmIdentity(identity) == nil)
        #expect(identity.draftValues[0] == "Tên Mẫu Đã Sửa")
        #expect(!live.idCardConfirmed && FileManager.default.fileExists(atPath: url.path))
        #expect(!server.captured.contains { $0.url?.lastPathComponent == "media" })
        server.enqueue("{\"received\":true}")
        #expect(await captures.confirmIdentity(identity) == .uploading)
        let sent = try SessionJSON.decoder().decode(IdCardFields.self, from: #require(server.captured.last?.httpBody))
        #expect(sent.fullName == "Tên Mẫu Đã Sửa" && sent.dateOfBirth == "1995-01-02" && sent.idNumber == fields.idNumber)
        server.enqueue(Fixtures.mediaAck); server.drop()
        await captures.face.submit()
        #expect(captures.face.retryUpload && live.mediaAcked && !live.signalsAcked)
        #expect(!FileManager.default.fileExists(atPath: url.path))
        server.enqueue(Fixtures.signalsAck); server.enqueue(Fixtures.pass)
        await captures.face.submit()
        #expect(captures.face.destination == .success && !captures.face.hasPendingCapture)
        let paths = server.captured.compactMap { $0.url?.lastPathComponent }
        #expect(paths.filter { $0 == "media" }.count == 1)
        #expect(paths.filter { $0 == "signals" }.count == 2)
        #expect(try #require(paths.firstIndex(of: "confirm")) < #require(paths.firstIndex(of: "media")))
        #expect(server.remainingReplies == 0 && server.unexpectedRequests == 0)
    }

    @Test(arguments: [false, true])
    func expiryDistinguishesChallengeAndSession(_ expiredSession: Bool) async throws {
        let server = MockServer(), captures = CaptureFlows()
        let identity = try await identity(server), live = try #require(identity.liveFlow)
        let url = try retain(captures.face, live: live)
        defer { captures.leaveFlow(live: live) }
        let parser = ISO8601DateFormatter()
        let now = try #require(parser.date(from: expiredSession ? "2100-01-01T00:00:01Z" : "2099-01-01T00:00:01Z"))
        #expect(captures.face.validatePendingCapture(now: now) == (expiredSession ? .errorSession : .faceExpired))
        #expect(!captures.face.hasPendingCapture && !FileManager.default.fileExists(atPath: url.path))
        #expect(identity.serverFields != nil && !identity.draftValues.isEmpty && live.requiresFreshChallenge)
    }

    @Test func rotatedChallengeRejectsOldCaptureBeforeAnyUpload() async throws {
        let server = MockServer(), captures = CaptureFlows()
        let identity = try await identity(server), live = try #require(identity.liveFlow)
        let url = try retain(captures.face, live: live)
        defer { captures.leaveFlow(live: live) }
        let session = try #require(live.session)
        var next = try #require(live.challenge); next = Challenge(challengeId: "ch_new_attempt", colorSequence: next.colorSequence,
            baselineMs: next.baselineMs, captureAtMs: next.captureAtMs, expiresAt: next.expiresAt, dynamic: next.dynamic)
        server.enqueue(try SessionJSON.encoder().encode(ChallengeResponse(token: "synthetic_rotated_value", expiresAt: session.expiresAt, challenge: next)))
        #expect(await live.prepareFace() == nil)
        let count = server.captured.count
        #expect(await captures.confirmIdentity(identity) == .faceExpired)
        #expect(server.captured.count == count && !FileManager.default.fileExists(atPath: url.path))
        #expect(!live.mediaAcked)
    }

    @Test(arguments: [Purpose.recovery, .reauth])
    func purposesWithoutCardCanUploadWithoutFakeFields(_ purpose: Purpose) async throws {
        let server = MockServer(), captures = CaptureFlows()
        let flow = LiveFlow(api: server.api())
        server.enqueue(try session())
        #expect(await flow.createSession(purpose: purpose) == nil)
        _ = try retain(captures.face, live: flow, purpose: purpose)
        defer { captures.leaveFlow(live: flow) }
        #expect(captures.face.stage == .readyToUpload && flow.idFields == nil)
        server.enqueue(Fixtures.mediaAck); server.enqueue(Fixtures.signalsAck); server.enqueue(Fixtures.pass)
        await captures.face.submit()
        #expect(captures.face.destination == .success)
        #expect(!server.captured.contains { $0.url?.lastPathComponent == "confirm" })
    }

    @Test func lateConfirmAfterAbandonCannotConfirmOrNavigateNewAttempt() async throws {
        let server = MockServer(), captures = CaptureFlows()
        let identity = try await identity(server), live = try #require(identity.liveFlow)
        let url = try retain(captures.face, live: live)
        let count = server.captured.count, gate = server.hold()
        let pending = Task { await captures.confirmIdentity(identity) }
        for _ in 0..<200 {
            if server.captured.count > count { break }
            try await Task.sleep(for: .milliseconds(10))
        }
        #expect(server.captured.count == count + 1)
        identity.cancelPendingRequests()
        captures.restartFace(live: live)
        gate.release("{\"received\":true}")
        #expect(await pending.value == nil)
        #expect(!live.idCardConfirmed && !captures.face.hasPendingCapture && captures.face.destination == nil)
        #expect(!FileManager.default.fileExists(atPath: url.path))
        captures.leaveFlow(live: live)
    }

    @Test func doubleConfirmHasOneRequestAndRejectedConfirmNeverUploads() async throws {
        let server = MockServer(), captures = CaptureFlows()
        let identity = try await identity(server), live = try #require(identity.liveFlow)
        _ = try retain(captures.face, live: live)
        defer { captures.leaveFlow(live: live) }
        let count = server.captured.count, gate = server.hold()
        let first = Task { await captures.confirmIdentity(identity) }
        for _ in 0..<200 {
            if server.captured.count > count { break }
            try await Task.sleep(for: .milliseconds(10))
        }
        try #require(server.captured.count == count + 1)
        #expect(await captures.confirmIdentity(identity) == nil)
        #expect(server.captured.count == count + 1)
        gate.release("{\"error_code\":\"step_not_allowed\",\"message\":\"synthetic\"}", status: 409)
        #expect(await first.value == .errorService)
        #expect(!live.idCardConfirmed && !captures.face.hasPendingCapture)
        #expect(!server.captured.contains { ["media", "signals", "finalize"].contains($0.url?.lastPathComponent ?? "") })
    }

    @Test func qualityRetryRetainsConfirmedIdentityAndUsesNewChallenge() async throws {
        let server = MockServer(), captures = CaptureFlows()
        let identity = try await identity(server), live = try #require(identity.liveFlow)
        _ = try retain(captures.face, live: live)
        defer { captures.leaveFlow(live: live) }
        server.enqueue("{\"received\":true}")
        #expect(await captures.confirmIdentity(identity) == .uploading)
        var next = try #require(live.challenge)
        next = Challenge(challengeId: "ch_quality_retry", colorSequence: next.colorSequence, baselineMs: next.baselineMs,
            captureAtMs: next.captureAtMs, expiresAt: next.expiresAt, dynamic: next.dynamic)
        server.enqueue(Fixtures.mediaAck); server.enqueue(Fixtures.signalsAck)
        server.enqueue(try SessionJSON.encoder().encode(FinalizeResponse(status: "retry", retryHint: "MORE_LIGHT", challenge: next)))
        await captures.face.submit()
        #expect(captures.face.destination == .retryQuality && live.idCardConfirmed)
        let count = server.captured.count
        #expect(await live.prepareFace() == nil)
        #expect(server.captured.count == count) // Response already supplied the next challenge.
        _ = try retain(captures.face, live: live)
        #expect(captures.face.stage == .readyToUpload && captures.face.destination == nil)
        #expect(live.challenge?.challengeId == "ch_quality_retry")
    }

    @Test func demoConfirmIsAfterFaceAndRestartDropsOldViews() throws {
        let demo = DemoFlow(), navigation = AppNavigation()
        let sequence = demo.routeSequence(for: .onboarding)
        #expect(try #require(sequence.firstIndex(of: .confirm)) > #require(sequence.firstIndex(of: .turnHead)))
        #expect(demo.afterHeadTurn() == .confirm)
        #expect(demo.confirmIdentity() == .voice && demo.afterHeadTurn() == .voice)
        for route in [Route.auth, .phone, .faceReady, .confirm, .editInfo] { navigation.go(route) }
        navigation.restartFace()
        #expect(navigation.path == [.auth, .phone, .faceReady])
    }

    @Test func dynamicBindingRejectsUnknownOrMalformedDeadline() throws {
        let current = try SessionJSON.decoder().decode(CreateSessionResponse.self, from: session())
        var challenge = current.challenge
        challenge.expiresAt = nil
        #expect(FaceAttemptBinding(session: current, challenge: challenge) == nil)
        challenge.expiresAt = "not-a-date"
        #expect(FaceAttemptBinding(session: current, challenge: challenge) == nil)
    }

    @Test func missingFileAndServerExpiredChallengeNeverUpload() async throws {
        let server = MockServer(), captures = CaptureFlows()
        let identity = try await identity(server), live = try #require(identity.liveFlow)
        var url = try retain(captures.face, live: live)
        defer { captures.leaveFlow(live: live) }
        try FileManager.default.removeItem(at: url)
        let count = server.captured.count
        #expect(await captures.confirmIdentity(identity) == .faceExpired)
        #expect(server.captured.count == count)
        let current = try #require(live.session), challenge = try #require(live.challenge)
        server.enqueue(try SessionJSON.encoder().encode(ChallengeResponse(token: "synthetic_fresh", expiresAt: current.expiresAt, challenge: challenge)))
        #expect(await live.prepareFace() == nil)
        url = try retain(captures.face, live: live)
        server.error(409, "challenge_expired")
        #expect(await captures.confirmIdentity(identity) == .faceExpired)
        #expect(!live.idCardConfirmed && !FileManager.default.fileExists(atPath: url.path))
        #expect(!server.captured.contains { $0.url?.lastPathComponent == "media" })
    }
}
