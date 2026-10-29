import Foundation
import Testing
@testable import VeriClue

@MainActor
struct LiveFlowStageATests {
    @Test func otpCreatesOneSessionAndShowsSMS() async throws {
        let server = MockServer()
        let flow = LiveFlow(api: server.api())
        server.enqueue(try Fixtures.session())
        server.enqueue("{\"expires_at\":\"2026-10-24T10:02:00Z\",\"attempts_left\":5,\"simulated_sms\":\"Mã xác minh 123456\"}")
        #expect(await flow.sendOtp(phone: "0912345678", purpose: .onboarding, scenario: "genuine") == nil)
        #expect(flow.otpSms == "Mã xác minh 123456")
        #expect(flow.attemptsLeft == 5)
        let create = try SessionJSON.decoder().decode(CreateSessionRequest.self, from: server.captured[0].httpBody!)
        #expect(create.purpose == "onboarding")
        #expect(create.nonce.range(of: "^[A-Za-z0-9_-]{16,128}$", options: .regularExpression) != nil)
        let otp = try SessionJSON.decoder().decode(OtpRequest.self, from: server.captured[1].httpBody!)
        #expect(otp.phone == "0912345678")
        server.enqueue("{\"expires_at\":\"2026-10-24T10:02:00Z\",\"attempts_left\":5}")
        #expect(await flow.sendOtp(phone: "0912345678") == nil)
        #expect(flow.otpSms == nil)
        #expect(server.captured.filter { $0.url!.path == "/v1/sessions" }.count == 1)
    }

    @Test func otpPassWrongLockedExpiredAndAlreadyVerified() async throws {
        let server = MockServer()
        let flow = LiveFlow(api: server.api())
        server.enqueue(try Fixtures.session())
        #expect(await flow.createSession() == nil)
        server.enqueue("{\"status\":\"retry\",\"attempts_left\":4}")
        #expect(await flow.verifyOtp(code: "000000") == .wrong(4))
        for code in ["otp_locked", "otp_expired", "otp_not_requested", "otp_too_many"] {
            server.error(409, code)
            #expect(await flow.verifyOtp(code: "000000") == .fail(.conflict(code: code)))
        }
        server.error(409, "otp_already_verified")
        #expect(await flow.verifyOtp(code: "123456") == .pass)
        server.enqueue("{\"status\":\"pass\",\"attempts_left\":4}")
        #expect(await flow.verifyOtp(code: "123456") == .pass)
        server.enqueue("{\"status\":\"unknown\",\"attempts_left\":4}")
        #expect(await flow.verifyOtp(code: "123456") == .fail(.badResponse))
    }

    @Test func idCardUploadsPhotosQRAndConfirmsFields() async throws {
        let server = MockServer()
        let flow = LiveFlow(api: server.api())
        server.enqueue(try Fixtures.session())
        #expect(await flow.createSession() == nil)
        server.enqueue("{\"status\":\"ok\",\"fields\":{\"full_name\":\"Nguyễn Văn An\",\"id_number\":\"001099012345\"}}")
        #expect(await flow.sendIdCard(front: Data([1]), back: Data([2]), qr: "qr text") == .accepted)
        #expect(flow.idFields?.idNumber == "001099012345")
        let request = server.captured.last!
        #expect(request.url!.path == "/v1/sessions/" + flow.session!.sessionId + "/id-card")
        let body = String(decoding: request.httpBody!, as: UTF8.self)
        for text in ["name=\"front\"", "name=\"back\"", "name=\"qr\"", "qr text"] { #expect(body.contains(text)) }
        let fields = flow.idFields!
        server.enqueue("{\"received\":true}")
        #expect(await flow.confirmIdCard(fields: fields) == nil)
        #expect(try SessionJSON.decoder().decode(IdCardFields.self, from: server.captured.last!.httpBody!) == fields)
        server.enqueue("{\"received\":false}")
        #expect(await flow.confirmIdCard(fields: fields) == .badResponse)
        server.error(409, "id_card_not_received")
        #expect(await flow.confirmIdCard(fields: fields) == .conflict(code: "id_card_not_received"))
        server.enqueue("{\"status\":\"retry\",\"retry_hint\":\"QR_INVALID\"}")
        #expect(await flow.sendIdCard(front: Data([1]), back: Data([2]), qr: nil) == .retry("QR_INVALID"))
        #expect(flow.idFields == nil)
        server.enqueue("{\"status\":\"unknown\"}")
        #expect(await flow.sendIdCard(front: Data([1]), back: Data([2]), qr: nil) == .fail(.badResponse))
        server.enqueue("{\"status\":\"ok\"}")
        #expect(await flow.sendIdCard(front: Data([1]), back: Data([2]), qr: nil) == .fail(.badResponse))
    }

    @Test func refreshRotatesTokenAndDropsStaleCapture() async throws {
        let server = MockServer()
        let flow = LiveFlow(api: server.api())
        server.enqueue(try Fixtures.session())
        #expect(await flow.prepareFace() == nil)
        #expect(server.captured.count == 1)
        flow.frontalJpeg = Data([1])
        flow.pendingWav = Data([2])
        flow.audioOffsetMs = 100
        server.enqueue("{\"token\":\"rotated_token\",\"expires_at\":\"2026-10-24T10:05:00Z\",\"challenge\":" + (try Fixtures.challenge()) + "}")
        #expect(await flow.prepareFace() == nil)
        #expect(flow.token == "rotated_token")
        #expect(flow.challenge?.challengeId == "ch_next")
        #expect(flow.session?.challenge == flow.challenge)
        #expect(flow.frontalJpeg == nil && flow.pendingWav == nil && flow.audioOffsetMs == nil)
        server.enqueue("{\"status\":\"pass\",\"attempts_left\":5}")
        #expect(await flow.verifyOtp(code: "123456") == .pass)
        #expect(server.captured.last!.value(forHTTPHeaderField: "Authorization") == "Bearer rotated_token")
        server.error(401, "bad_token")
        #expect(await flow.prepareFace() == .unauthorized)
        #expect(flow.token == "rotated_token")
        flow.dropFaceAttempt()
        #expect(flow.session != nil)
        flow.reset()
        #expect(flow.session == nil && flow.token == nil && flow.challenge == nil)
    }

    @Test func malformedRefreshDoesNotReplaceToken() async throws {
        let server = MockServer()
        let flow = LiveFlow(api: server.api())
        server.enqueue(try Fixtures.session())
        #expect(await flow.createSession() == nil)
        let old = flow.token
        server.enqueue("{\"expires_at\":\"2026-10-24T10:05:00Z\",\"challenge\":" + (try Fixtures.challenge()) + "}")
        #expect(await flow.prepareFace() == .badResponse)
        #expect(flow.token == old)
    }

    @Test func noSessionAndEmptyVoiceNeverPass() async throws {
        let server = MockServer()
        let flow = LiveFlow(api: server.api())
        #expect(await flow.submitFace() == .fail(.expired))
        #expect(await flow.verifyOtp(code: "123456") == .fail(.expired))
        #expect(await flow.submitVoice(wav: Data()) == .fail(.expired))
        server.enqueue(try Fixtures.session())
        #expect(await flow.createSession() == nil)
        #expect(await flow.submitVoice(wav: Data()) == .to(.noVoice))
        #expect(server.captured.count == 1)
    }
}
