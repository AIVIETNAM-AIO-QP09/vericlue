import Foundation
import Testing
@testable import VeriClue

@MainActor
struct FaceCaptureIntegrationTests {
    @Test func fullSignalsPayloadUsesRotatedTokenAndRetriesOnlyUnreceivedSignals() async throws {
        let server = MockServer()
        let live = LiveFlow(api: server.api())
        let response = try SessionJSON.decoder().decode(CreateSessionResponse.self, from: Fixtures.session(dynamic: true))
        server.enqueue(try Fixtures.session(dynamic: true))
        #expect(await live.createSession(purpose: .onboarding, scenario: "genuine") == nil)
        let rotated = Challenge(challengeId: "ch_ios04_rotated", colorSequence: response.challenge.colorSequence,
            baselineMs: response.challenge.baselineMs, captureAtMs: response.challenge.captureAtMs,
            expiresAt: response.challenge.expiresAt, dynamic: response.challenge.dynamic)
        server.enqueue(try SessionJSON.encoder().encode(ChallengeResponse(token: "ios04_fixture_not_a_valid_token",
            expiresAt: response.expiresAt, challenge: rotated)))
        #expect(await live.prepareFace() == nil)
        live.frontalJpeg = Data([0xff, 0xd8, 0xff, 0xd9]) // Synthetic API bytes; not a JPEG validity test.
        live.colorEvents = [ColorEvent(index: 0, rgb: "#80e09e", paintedAt: 11000)]
        let frames = [FrameTime(captureTime: 10000, presentedFrames: 1, mediaTime: 0)]
        let region: [String: JSONValue] = ["t_ms": .number(10000), "regions": .object(["synthetic": .bool(true)])]
        let probe = CamProbe(apiTamperFlags: [], deviceLabel: "synthetic iPhone", duplicateFrameRatio: 0)
        server.enqueue(Fixtures.mediaAck)
        server.drop() // Media accepted; signals transport fails.
        #expect(await live.submitFace(video: Data("synthetic MP4 API bytes".utf8), frameTimes: frames,
                                      camprobe: probe, regionMeans: [region]) == .fail(.network))
        #expect(live.mediaAcked && !live.signalsAcked)
        #expect(live.pendingFaceVideo == nil)
        server.enqueue(Fixtures.signalsAck)
        server.enqueue("{\"status\":\"voice_challenge\",\"voice_prompt\":\"Câu đọc từ server\",\"voice_challenge_id\":\"vc_fixture\"}")
        #expect(await live.submitFace() == .to(.voice))
        let requests = server.captured
        #expect(requests.filter { $0.url?.lastPathComponent == "media" }.count == 1)
        let signalRequests = requests.filter { $0.url?.lastPathComponent == "signals" }
        #expect(signalRequests.count == 2)
        let firstSignals = try SessionJSON.decoder().decode(Signals.self, from: #require(signalRequests[0].httpBody))
        let signals = try SessionJSON.decoder().decode(Signals.self, from: #require(signalRequests.last?.httpBody))
        #expect(firstSignals == signals)
        #expect(signals.frameTimes == frames && signals.regionMeans == [region] && signals.camprobe == probe)
        #expect(signals.challengeId == rotated.challengeId)
        #expect(requests.dropFirst(2).allSatisfy { $0.value(forHTTPHeaderField: "Authorization") == "Bearer ios04_fixture_not_a_valid_token" })
        #expect(live.voicePrompt == "Câu đọc từ server" && live.voiceChallengeId == "vc_fixture")
        #expect(server.remainingReplies == 0 && server.unexpectedRequests == 0)
    }

    @Test func reenteringFaceClearsOldDestinationAndUnauthorizedCannotStartCamera() async throws {
        let server = MockServer()
        let live = LiveFlow(api: server.api())
        server.enqueue(try Fixtures.session(dynamic: true))
        #expect(await live.createSession(purpose: .onboarding) == nil)
        let face = FaceCaptureFlow()
        face.configure(live: live, purpose: .onboarding)
        server.error(401, "fixture_expired")
        await face.prepare()
        #expect(face.destination == .errorSession)
        #expect(!face.camera.running && !face.camera.recording)
        face.configure(live: live, purpose: .onboarding)
        #expect(face.destination == nil && face.stage == .intro)
        face.cancel()
    }
}
