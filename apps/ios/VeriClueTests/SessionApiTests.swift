import Foundation
import Testing
@testable import VeriClue

@MainActor
struct SessionApiTests {
    @Test func HTTPStatusMappingAndServerCodeArePreserved() async throws {
        let mappings: [(Int, ApiError)] = [(401, .unauthorized), (409, .conflict(code: "session_closed")), (410, .expired), (422, .badResponse), (429, .busy), (503, .busy), (500, .server)]
        let server = MockServer()
        let api = server.api()
        for (status, expected) in mappings {
            server.error(status, "session_closed")
            #expect(await api.createSession() == .failure(expected))
        }
        server.enqueue("not JSON", status: 409)
        #expect(await api.createSession() == .failure(.conflict(code: nil)))
        server.enqueue("{}")
        #expect(await api.createSession() == .failure(.badResponse))
        server.drop()
        #expect(await api.createSession() == .failure(.network))
        #expect(server.captured.count == mappings.count + 3)
    }

    @Test func allEndpointsUsePostAndSessionBearer() async throws {
        let server = MockServer()
        let api = server.api()
        server.enqueue(try Fixtures.session())
        let created = try await api.createSession().get()
        #expect(server.captured[0].httpMethod == "POST")
        #expect(server.captured[0].value(forHTTPHeaderField: "Authorization") == nil)
        let id = created.sessionId
        let token = created.token
        server.enqueue("{\"expires_at\":\"2026-10-24T10:00:00Z\",\"attempts_left\":5}")
        _ = try await api.sendOtp(sessionId: id, token: token, phone: "0912345678").get()
        server.enqueue("{\"status\":\"pass\",\"attempts_left\":5}")
        _ = try await api.verifyOtp(sessionId: id, token: token, code: "123456").get()
        server.enqueue("{\"status\":\"ok\",\"fields\":{}}")
        _ = try await api.sendIdCard(sessionId: id, token: token, front: Data([1]), back: Data([2]), qr: nil).get()
        server.enqueue("{\"received\":true}")
        _ = try await api.confirmIdCard(sessionId: id, token: token, fields: IdCardFields()).get()
        server.enqueue("{\"token\":\"new\",\"expires_at\":\"2026-10-24T10:00:00Z\",\"challenge\":" + (try Fixtures.challenge()) + "}")
        _ = try await api.refreshChallenge(sessionId: id, token: token).get()
        server.enqueue(Fixtures.mediaAck)
        _ = try await api.sendMedia(sessionId: id, token: token, imageJpeg: Data([1]), video: Data([2]), challengeId: "ch_1").get()
        server.enqueue(Fixtures.signalsAck)
        _ = try await api.sendSignals(sessionId: id, token: token, signals: Signals(colorEvents: [], frameTimes: [], challengeId: "ch_1")).get()
        server.enqueue(Fixtures.pass)
        _ = try await api.finalize(sessionId: id, token: token, challengeId: "ch_1").get()
        server.enqueue(Fixtures.pass)
        _ = try await api.sendVoice(sessionId: id, token: token, wav: Data([1]), video: Data([2]), audioOffsetMs: -20, voiceChallengeId: "vc_1").get()
        let suffixes = ["otp", "otp/verify", "id-card", "id-card/confirm", "challenge", "media", "signals", "finalize", "voice"]
        for (request, suffix) in zip(server.captured.dropFirst(), suffixes) {
            #expect(request.httpMethod == "POST")
            #expect(request.url!.path == "/v1/sessions/" + id + "/" + suffix)
            #expect(request.value(forHTTPHeaderField: "Authorization") == "Bearer " + token)
            #expect(request.value(forHTTPHeaderField: "X-Mock-Scenario") == nil)
        }
        #expect(server.remainingReplies == 0 && server.unexpectedRequests == 0)
    }

    @Test func multipartPreservesBinaryCRLFAndVoiceMetadata() async throws {
        var multipart = MultipartBody()
        let binary = Data([0, 13, 10, 255, 128])
        multipart.file("image", filename: "face.jpg", contentType: "image/jpeg", data: binary)
        multipart.field("challenge_id", "ch_1")
        #expect(multipart.data.range(of: binary) != nil)
        #expect(multipart.data.starts(with: Data(("--" + multipart.boundary + "\r\n").utf8)))
        #expect(multipart.data.suffix(multipart.boundary.utf8.count + 6) == Data(("--" + multipart.boundary + "--\r\n").utf8))
        let server = MockServer()
        let api = server.api()
        #expect(await api.sendVoice(sessionId: "s", token: "t", wav: binary, video: binary, audioOffsetMs: 5001, voiceChallengeId: "v") == .failure(.badResponse))
        #expect(await api.sendVoice(sessionId: "s", token: "t", wav: binary, video: nil, audioOffsetMs: 10, voiceChallengeId: "v") == .failure(.badResponse))
        #expect(server.captured.isEmpty)
        server.enqueue(Fixtures.pass)
        _ = try await api.sendVoice(sessionId: "s", token: "t", wav: binary, video: binary, audioOffsetMs: 640, voiceChallengeId: "vc_1").get()
        let request = server.captured[0]
        #expect(request.httpBody!.range(of: binary) != nil)
        let text = String(decoding: request.httpBody!, as: UTF8.self)
        for expected in ["name=\"audio\"", "name=\"video\"", "audio/wav", "video/mp4", "name=\"audio_offset_ms\"\r\n\r\n640", "name=\"voice_challenge_id\"\r\n\r\nvc_1"] { #expect(text.contains(expected)) }
    }

    @Test func timeoutsAndOfflineTransport() async {
        let config = SessionApi.configuration()
        #expect(config.timeoutIntervalForRequest == 15)
        #expect(config.timeoutIntervalForResource == 60)
        #expect(!config.waitsForConnectivity)
        let server = MockServer()
        server.enqueue("{}")
        #expect(await server.api().createSession() == .failure(.badResponse))
        #expect(server.captured[0].url!.host!.hasSuffix(".invalid"))
        // No script exists for this URL: it fails inside the mock, without a network fallback.
        #expect(await server.api().createSession() == .failure(.network))
        #expect(server.unexpectedRequests == 1)
    }
}
