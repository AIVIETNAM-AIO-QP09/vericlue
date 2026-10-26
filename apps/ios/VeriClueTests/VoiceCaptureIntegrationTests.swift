import Foundation
import Testing
@testable import VeriClue

@MainActor
struct VoiceCaptureIntegrationTests {
    private func prepared(_ server: MockServer) async throws -> LiveFlow {
        let live = LiveFlow(api: server.api())
        server.enqueue(try Fixtures.session(dynamic: true))
        #expect(await live.createSession(purpose: .onboarding, scenario: "voice_clone") == nil)
        live.frontalJpeg = Data([1, 2, 3]) // Synthetic transport bytes, no personal media.
        server.enqueue(Fixtures.mediaAck); server.enqueue(Fixtures.signalsAck)
        server.enqueue("{\"status\":\"voice_challenge\",\"voice_prompt\":\"Câu mẫu tổng hợp\",\"voice_challenge_id\":\"vc_synthetic_first\",\"attempts_left\":1}")
        #expect(await live.submitFace() == .to(.voice))
        return live
    }

    @Test func networkRetryKeepsSameWavVideoOffsetAndChallengeThenReview() async throws {
        let server = MockServer()
        let live = try await prepared(server)
        let wav = try WavPCM.encode(Data(repeating: 42, count: 3200))
        let video = Data("synthetic MP4 transport only".utf8)
        var accepted = 0
        server.drop()
        #expect(await live.submitVoice(wav: wav, video: video, audioOffsetMs: 125,
                                       onAccepted: { accepted += 1 }) == .fail(.network))
        #expect(accepted == 0 && !live.voiceChecked)
        #expect(live.pendingWav == wav && live.pendingVoiceVideo == video)
        server.enqueue("{\"status\":\"review\"}")
        // Different arguments must not replace the unacknowledged payload.
        #expect(await live.submitVoice(wav: Data([99]), video: Data([88]), audioOffsetMs: 999,
                                       onAccepted: { accepted += 1 }) == .to(.review))
        let requests = server.captured.filter { $0.url?.lastPathComponent == "voice" }
        #expect(requests.count == 2)
        for request in requests {
            let body = try #require(request.httpBody)
            let text = String(decoding: body, as: UTF8.self)
            #expect(body.range(of: wav) != nil && body.range(of: video) != nil)
            #expect(text.contains("name=\"audio_offset_ms\"\r\n\r\n125\r\n"))
            #expect(text.contains("vc_synthetic_first"))
            #expect(request.value(forHTTPHeaderField: "Authorization") == "Bearer " + live.token!)
        }
        #expect(accepted == 1 && live.voiceChecked)
        #expect(live.pendingWav == nil && live.pendingVoiceVideo == nil)
        #expect(server.remainingReplies == 0 && server.unexpectedRequests == 0)
    }

    @Test func zeroRemainingAllowsIssuedFinalReadButNotAnotherPrompt() async throws {
        let server = MockServer()
        let live = try await prepared(server)
        server.enqueue("{\"status\":\"voice_challenge\",\"voice_prompt\":\"Câu đọc lại cuối\",\"voice_challenge_id\":\"vc_synthetic_second\",\"attempts_left\":0}")
        #expect(await live.submitVoice(wav: Data([1])) == .to(.voiceAgain))
        #expect(live.attemptsLeft == 0 && live.voiceChallengeId == "vc_synthetic_second")
        server.enqueue("{\"status\":\"voice_challenge\",\"voice_prompt\":\"Không được lặp vô hạn\",\"voice_challenge_id\":\"vc_synthetic_third\",\"attempts_left\":0}")
        #expect(await live.submitVoice(wav: Data([2])) == .fail(.badResponse))
        #expect(live.voiceChallengeId == "vc_synthetic_second")
    }

    @Test func reusedPromptIdAndReceiptConflictNeverBecomeSuccess() async throws {
        let server = MockServer()
        let live = try await prepared(server)
        server.enqueue("{\"status\":\"voice_challenge\",\"voice_prompt\":\"Câu khác\",\"voice_challenge_id\":\"vc_synthetic_first\",\"attempts_left\":0}")
        #expect(await live.submitVoice(wav: Data([1])) == .fail(.badResponse))
        server.error(409, "step_already_received")
        #expect(await live.submitVoice(wav: Data([1])) == .fail(.conflict(code: "step_already_received")))
        #expect(!live.voiceChecked)
    }

    @Test func emptyAudioDoesNotSendRequestOrOpenCamera() async throws {
        let server = MockServer()
        let live = try await prepared(server)
        let count = server.captured.count
        #expect(await live.submitVoice(wav: Data()) == .to(.noVoice))
        #expect(server.captured.count == count)
        let camera = FrontCameraSession()
        let voice = VoiceCaptureFlow(camera: camera)
        #expect(voice.camera === camera)
        voice.configure(live: nil, screenID: UUID())
        await voice.start()
        #expect(voice.stage == .failed && voice.destination == nil)
        #expect(!camera.running && !camera.recording)
    }

    @Test func rootSharesExactlyTheSameCameraAndOldScreenCannotCancelNewOne() async {
        let flows = CaptureFlows()
        #expect(flows.face.camera === flows.voice.camera)
        let old = UUID(), current = UUID()
        flows.voice.configure(live: nil, screenID: old)
        flows.voice.configure(live: nil, screenID: current)
        await flows.voice.start() // No live session: fail before requesting device access.
        flows.voice.leaveScreen(old)
        #expect(flows.voice.stage == .failed && !flows.voice.camera.running)
    }
}
