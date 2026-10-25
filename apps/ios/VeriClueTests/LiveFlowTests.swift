import Foundation
import Testing
@testable import VeriClue

@MainActor
struct LiveFlowTests {
    private func capturedFlow(_ server: MockServer, dynamic: Bool = false) async throws -> LiveFlow {
        let flow = LiveFlow(api: server.api())
        server.enqueue(try Fixtures.session(dynamic: dynamic))
        #expect(await flow.createSession(purpose: dynamic ? .onboarding : nil, scenario: "genuine") == nil)
        flow.frontalJpeg = Data([1, 2, 3])
        return flow
    }

    private func final(_ server: MockServer, _ value: String) {
        server.enqueue(Fixtures.mediaAck)
        server.enqueue(Fixtures.signalsAck)
        server.enqueue(value)
    }

    @Test func passSendsTokenScenarioAndChallenge() async throws {
        let server = MockServer()
        let flow = try await capturedFlow(server)
        final(server, Fixtures.pass)
        #expect(await flow.submitFace() == .to(.success))
        let requests = server.captured
        let sessionId = try #require(flow.session?.sessionId)
        #expect(requests.map { $0.url!.path } == ["/v1/sessions", "/v1/sessions/" + sessionId + "/media", "/v1/sessions/" + sessionId + "/signals", "/v1/sessions/" + sessionId + "/finalize"])
        #expect(requests[0].value(forHTTPHeaderField: "X-Mock-Scenario") == "genuine")
        #expect(requests.dropFirst().allSatisfy { $0.value(forHTTPHeaderField: "Authorization") == "Bearer " + flow.token! })
        #expect(String(decoding: requests[1].httpBody!, as: UTF8.self).contains("name=\"challenge_id\""))
        let request = try SessionJSON.decoder().decode(FinalizeRequest.self, from: requests[3].httpBody!)
        #expect(request.challengeId == flow.challenge?.challengeId)
        #expect(server.remainingReplies == 0)
        #expect(server.unexpectedRequests == 0)
    }

    @Test func voiceChallengeKeepsPromptAndId() async throws {
        let server = MockServer()
        let flow = try await capturedFlow(server, dynamic: true)
        final(server, "{\"status\":\"voice_challenge\",\"voice_prompt\":\"Tôi xác nhận\",\"voice_challenge_id\":\"vc_first\"}")
        #expect(await flow.submitFace() == .to(.voice))
        #expect(flow.voicePrompt == "Tôi xác nhận")
        #expect(flow.voiceChallengeId == "vc_first")
        var accepted = 0
        server.enqueue("{\"status\":\"voice_challenge\",\"voice_prompt\":\"Câu mới\",\"voice_challenge_id\":\"vc_next\",\"attempts_left\":1}")
        #expect(await flow.submitVoice(wav: Data([1, 2]), video: Data([9, 9]), audioOffsetMs: 640, onAccepted: { accepted += 1 }) == .to(.voiceAgain))
        let body = String(decoding: server.captured.last!.httpBody!, as: UTF8.self)
        for value in ["name=\"audio\"", "name=\"video\"", "video/mp4", "name=\"audio_offset_ms\"", "640", "vc_first"] {
            #expect(body.contains(value))
        }
        #expect(accepted == 1)
        #expect(flow.voiceChallengeId == "vc_next")
        #expect(flow.voicePrompt == "Câu mới")
        #expect(flow.attemptsLeft == 1)
        #expect(flow.pendingWav == nil)
        #expect(flow.voiceChecked)
        server.enqueue(Fixtures.pass)
        #expect(await flow.submitVoice(wav: Data([3])) == .to(.success))
        #expect(String(decoding: server.captured.last!.httpBody!, as: UTF8.self).contains("vc_next"))
    }

    @Test(arguments: ["degraded", "error", "", "unexpected"])
    func unknownStatusIsNeverSuccess(_ status: String) async throws {
        let server = MockServer()
        let flow = try await capturedFlow(server)
        final(server, "{\"status\":\"" + status + "\"}")
        #expect(await flow.submitFace() == .fail(.badResponse))
        server.enqueue("{\"status\":\"" + status + "\"}")
        #expect(await flow.submitVoice(wav: Data([1])) == .fail(.badResponse))
        #expect(!flow.voiceChecked)
        #expect(flow.pendingWav == Data([1]))
    }

    @Test func brokenJSONAndUnauthorizedAreErrors() async throws {
        let server = MockServer()
        let flow = try await capturedFlow(server)
        server.enqueue("{broken")
        #expect(await flow.submitFace() == .fail(.badResponse))
        server.error(401, "expired")
        #expect(await flow.submitFace() == .fail(.unauthorized))
        #expect(!flow.mediaAcked)
        #expect(FlowRules.errorRoute(.unauthorized) == .errorSession)
    }

    @Test func noNetworkIsAnErrorWithoutAutomaticRetry() async {
        let server = MockServer()
        let flow = LiveFlow(api: server.api())
        server.drop()
        #expect(await flow.createSession() == .network)
        #expect(flow.session == nil)
        #expect(server.captured.count == 1)
    }

    @Test func retryNeedsChallengeAndVoiceNeedsRequiredFields() async throws {
        for body in ["{\"status\":\"retry\"}", "{\"status\":\"voice_challenge\"}", "{\"status\":\"voice_challenge\",\"voice_prompt\":\"Câu đọc\"}"] {
            let server = MockServer()
            let flow = try await capturedFlow(server, dynamic: true)
            final(server, body)
            #expect(await flow.submitFace() == .fail(.badResponse))
        }
    }

    @Test func falseWrongAndMissingAcknowledgmentsFail() async throws {
        for body in ["{\"step\":\"media\",\"received\":false}", "{\"step\":\"signals\",\"received\":true}", "{\"step\":\"media\"}"] {
            let server = MockServer()
            let flow = try await capturedFlow(server)
            server.enqueue(body)
            #expect(await flow.submitFace() == .fail(.badResponse))
            #expect(!flow.mediaAcked)
            #expect(server.captured.count == 2)
        }
    }

    @Test(arguments: [0, 1, 2])
    func networkRetryResendsOnlyUnacknowledgedSteps(_ failureIndex: Int) async throws {
        let server = MockServer()
        let flow = try await capturedFlow(server)
        let replies = [Fixtures.mediaAck, Fixtures.signalsAck, Fixtures.pass]
        for reply in replies.prefix(failureIndex) { server.enqueue(reply) }
        server.drop()
        #expect(await flow.submitFace(video: Data([7])) == .fail(.network))
        #expect(flow.mediaAcked == (failureIndex > 0))
        #expect(flow.signalsAcked == (failureIndex > 1))
        for reply in replies.dropFirst(failureIndex) { server.enqueue(reply) }
        #expect(await flow.submitFace() == .to(.success))
        let paths = server.captured.dropFirst().map { $0.url!.lastPathComponent }
        let all = ["media", "signals", "finalize"]
        #expect(paths == Array(all.prefix(failureIndex + 1)) + Array(all.dropFirst(failureIndex)))
        #expect(server.unexpectedRequests == 0)
    }

    @Test(arguments: ["session_closed", "challenge_mismatch", "challenge_expired", "session_too_long", "voice_not_requested", "already_finalized", "unknown"])
    func nonReceiptConflictsNeverAcknowledge(_ code: String) async throws {
        let server = MockServer()
        let flow = try await capturedFlow(server)
        server.error(409, code)
        #expect(await flow.submitFace() == .fail(.conflict(code: code)))
        #expect(!flow.mediaAcked)
        #expect(!flow.signalsAcked)
    }

    @Test(arguments: [0, 1])
    func onlyStepAlreadyReceivedIsAnAcknowledgment(_ failureIndex: Int) async throws {
        let server = MockServer()
        let flow = try await capturedFlow(server)
        if failureIndex == 1 { server.enqueue(Fixtures.mediaAck) }
        server.drop()
        #expect(await flow.submitFace() == .fail(.network))
        server.error(409, "step_already_received")
        if failureIndex == 0 { server.enqueue(Fixtures.signalsAck) }
        server.enqueue(Fixtures.pass)
        #expect(await flow.submitFace() == .to(.success))
        #expect(flow.mediaAcked && flow.signalsAcked)
    }

    @Test func finalizeConflictIsNotReceiptOrSuccess() async throws {
        let server = MockServer()
        let flow = try await capturedFlow(server)
        server.enqueue(Fixtures.mediaAck)
        server.enqueue(Fixtures.signalsAck)
        server.drop()
        #expect(await flow.submitFace() == .fail(.network))
        server.error(409, "step_already_received")
        #expect(await flow.submitFace() == .fail(.conflict(code: "step_already_received")))
        #expect(server.captured.suffix(2).allSatisfy { $0.url!.lastPathComponent == "finalize" })
    }

    @Test func retryAfterNetworkNeverPassesOnAnyNonPassStatus() async throws {
        let bodies = [
            "{\"status\":\"retry\",\"challenge\":" + (try Fixtures.challenge()) + "}",
            "{\"status\":\"review\"}", "{\"status\":\"deny\"}", "{\"status\":\"recovery_required\"}",
            "{\"status\":\"voice_challenge\",\"voice_prompt\":\"Câu đọc\"}",
            "{\"status\":\"degraded\"}", "{\"status\":\"error\"}", "{\"status\":\"unknown\"}"
        ]
        for index in 0...2 {
            for body in bodies {
                let server = MockServer()
                let flow = try await capturedFlow(server)
                let replies = [Fixtures.mediaAck, Fixtures.signalsAck, body]
                for reply in replies.prefix(index) { server.enqueue(reply) }
                server.drop()
                #expect(await flow.submitFace() == .fail(.network))
                for reply in replies.dropFirst(index) { server.enqueue(reply) }
                #expect(await flow.submitFace() != .to(.success))
                #expect(server.unexpectedRequests == 0)
            }
        }
    }

    @Test func voiceNetworkErrorKeepsExactRecordingVideoAndOffset() async throws {
        let server = MockServer()
        let flow = try await capturedFlow(server)
        server.drop()
        #expect(await flow.submitVoice(wav: Data([9, 8]), video: Data([7]), audioOffsetMs: 640) == .fail(.network))
        #expect(flow.pendingWav == Data([9, 8]))
        #expect(flow.pendingVoiceVideo == Data([7]))
        #expect(!flow.voiceChecked)
        server.enqueue(Fixtures.pass)
        #expect(await flow.submitVoice(wav: Data([99]), video: Data([99]), audioOffsetMs: 0) == .to(.success))
        let bodies = server.captured.suffix(2).map { String(decoding: $0.httpBody!, as: UTF8.self) }
        #expect(bodies.allSatisfy { $0.contains("640") })
        #expect(flow.pendingWav == nil && flow.pendingVoiceVideo == nil)
        #expect(flow.voiceChecked)
    }

    @Test func retryReplacesChallengeAndResetsAcks() async throws {
        let server = MockServer()
        let flow = try await capturedFlow(server)
        final(server, "{\"status\":\"retry\",\"retry_hint\":\"MORE_LIGHT\",\"attempts_left\":1,\"challenge\":" + (try Fixtures.challenge()) + "}")
        var released = 0
        #expect(await flow.submitFace(video: Data([9]), onMediaAcked: { released += 1 }) == .to(.retryQuality))
        #expect(flow.challenge?.challengeId == "ch_next")
        #expect(flow.session?.challenge.challengeId == "ch_next")
        #expect(!flow.mediaAcked && !flow.signalsAcked)
        #expect(flow.frontalJpeg == nil && flow.colorEvents.isEmpty)
        #expect(flow.attemptsLeft == 1 && flow.retryHint == "MORE_LIGHT")
        #expect(released == 1)
        #expect(await flow.prepareFace() == nil)
        #expect(server.captured.count == 4) // No redundant /challenge after finalize retry.
        flow.frontalJpeg = Data([4])
        final(server, Fixtures.pass)
        #expect(await flow.submitFace() == .to(.success))
        #expect(server.captured[4].url!.lastPathComponent == "media")
    }

    @Test func localVideoReleasedOnlyAfterReceipt() async throws {
        let server = MockServer()
        let flow = try await capturedFlow(server)
        var released = 0
        server.drop()
        #expect(await flow.submitFace(video: Data([9]), onMediaAcked: { released += 1 }) == .fail(.network))
        #expect(released == 0)
        #expect(flow.pendingFaceVideo == Data([9]))
        final(server, Fixtures.pass)
        #expect(await flow.submitFace(onMediaAcked: { released += 1 }) == .to(.success))
        #expect(released == 1 && flow.pendingFaceVideo == nil)
    }
}
