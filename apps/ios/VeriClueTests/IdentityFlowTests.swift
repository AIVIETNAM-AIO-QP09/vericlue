import Foundation
import Testing
@testable import VeriClue

@MainActor
struct IdentityFlowTests {
    private let qr = "000000000001||NGUYEN VAN MAU|01011995|Nam|DIA CHI MAU|01012021"

    private func verified(_ server: MockServer) async throws -> IdentityFlow {
        let identity = IdentityFlow(api: server.api())
        identity.begin(purpose: .onboarding, scenario: "genuine")
        identity.phone = "0912345678"
        server.enqueue(try Fixtures.session())
        server.enqueue("{\"expires_at\":\"2026-10-24T10:00:00Z\",\"attempts_left\":5,\"simulated_sms\":\"Mã mô phỏng 123456\"}")
        #expect(await identity.sendOTP() == .otp)
        identity.code = "123456"
        server.enqueue("{\"status\":\"pass\",\"attempts_left\":5}")
        #expect(await identity.verifyOTP() == .idFront)
        return identity
    }

    @Test func resendUsesAbsoluteDeadlineIncludingBackgroundTime() {
        let start = Date(timeIntervalSince1970: 1000)
        var clock = OTPResendClock()
        #expect(clock.remaining(at: start) == 0)
        clock.sent(at: start)
        #expect(clock.remaining(at: start) == 45)
        #expect(clock.remaining(at: start.addingTimeInterval(0.5)) == 45)
        #expect(clock.remaining(at: start.addingTimeInterval(44.9)) == 1)
        #expect(clock.remaining(at: start.addingTimeInterval(45)) == 0)
        #expect(clock.remaining(at: start.addingTimeInterval(120)) == 0)
        clock.sent(at: start.addingTimeInterval(120))
        #expect(clock.remaining(at: start.addingTimeInterval(120)) == 45)
    }

    @Test func phoneValidationAndResendGateDoNotSendRequestsEarly() async throws {
        let server = MockServer()
        let identity = IdentityFlow(api: server.api())
        for phone in ["", "09123", "1912345678", "09abcdefgh", "０９１２３４５６７８"] {
            identity.phone = phone
            #expect(await identity.sendOTP() == nil)
        }
        #expect(server.captured.isEmpty)
        identity.phone = "0912345678"
        server.enqueue(try Fixtures.session())
        server.enqueue("{\"expires_at\":\"2026-10-24T10:00:00Z\",\"attempts_left\":5,\"simulated_sms\":\"Mã 123456\"}")
        #expect(await identity.sendOTP() == .otp)
        #expect(identity.otpSMS == "Mã 123456")
        #expect(await identity.sendOTP(resend: true) == nil)
        #expect(await identity.sendOTP() == .otp) // Back to phone must not bypass cooldown.
        #expect(server.captured.count == 2)
        server.enqueue("{\"expires_at\":\"2026-10-24T10:01:00Z\",\"attempts_left\":5,\"simulated_sms\":\"Mã 654321\"}")
        #expect(await identity.sendOTP(resend: true, now: Date().addingTimeInterval(46)) == .otp)
        #expect(identity.otpSMS == "Mã 654321")
        #expect(server.captured.count == 3)
        #expect(identity.resendClock.remaining() > 0)
    }

    @Test func changedPhoneCannotReuseOldCooldownAfterNetworkFailure() async throws {
        let server = MockServer()
        let identity = try await verified(server)
        #expect(identity.resendClock.remaining() > 0)
        identity.phone = "0987654321"
        server.enqueue(try Fixtures.session())
        server.drop()
        #expect(await identity.sendOTP() == nil)
        #expect(identity.resendClock.remaining() == 0)
        #expect(identity.otpSMS == nil && identity.code.isEmpty && !identity.otpVerified)
        #expect(!identity.otpHasError && !identity.otpLocked)
        #expect(identity.errorText != nil)
        server.enqueue("{\"expires_at\":\"2026-10-25T10:00:00Z\",\"attempts_left\":5,\"simulated_sms\":\"Mã mới 654321\"}")
        #expect(await identity.sendOTP() == .otp)
        #expect(identity.otpSMS == "Mã mới 654321")
        #expect(server.captured.count == 6)
        #expect(server.captured.last?.url?.path.hasSuffix("/otp") == true)
        let phone = try #require(server.captured.last?.httpBody)
        #expect(try SessionJSON.decoder().decode(OtpRequest.self, from: phone).phone == "0987654321")
        #expect(server.remainingReplies == 0)
    }

    @Test func wrongExpiredLockedTooManyAndAlreadyVerified() async throws {
        let server = MockServer()
        let identity = try await verified(server)
        identity.code = "000000"
        server.enqueue("{\"status\":\"retry\",\"attempts_left\":4}")
        #expect(await identity.verifyOTP() == nil)
        #expect(identity.attemptsLeft == 4)
        #expect(identity.errorText == FlowRules.otpWrongText(4))
        identity.appendCode("1")
        #expect(identity.code == "1" && !identity.otpHasError)
        identity.code = "000000"
        server.error(409, "otp_expired")
        #expect(await identity.verifyOTP() == nil)
        #expect(identity.otpLocked && identity.errorText == FlowRules.otpErrorText("otp_expired"))
        server.enqueue("{\"expires_at\":\"2026-10-24T10:01:00Z\",\"attempts_left\":5}")
        #expect(await identity.sendOTP(resend: true, now: Date().addingTimeInterval(46)) == .otp)
        identity.code = "000000"
        server.error(409, "otp_locked")
        #expect(await identity.verifyOTP() == nil)
        #expect(identity.attemptsLeft == 0 && identity.otpLocked)
        server.error(409, "otp_too_many")
        #expect(await identity.sendOTP(resend: true, now: Date().addingTimeInterval(46)) == .errorService)
        server.error(409, "otp_already_verified")
        #expect(await identity.sendOTP(resend: true, now: Date().addingTimeInterval(46)) == .idFront)
    }

    @Test func serverQRRetryReturnsToBackAndKeepsFront() async throws {
        let server = MockServer()
        let identity = try await verified(server)
        let front = IDCardPhoto(jpeg: Data([1, 2]), sharpness: 100, glareFraction: 0, qr: nil)
        let back = IDCardPhoto(jpeg: Data([3, 4]), sharpness: 100, glareFraction: 0, qr: qr)
        identity.acceptPhoto(front, isBack: false)
        identity.acceptPhoto(back, isBack: true)
        server.enqueue("{\"status\":\"retry\",\"retry_hint\":\"QR_INVALID\"}")
        #expect(await identity.uploadCard() == .idBack)
        #expect(identity.frontPhoto?.jpeg == front.jpeg && identity.backPhoto == nil)
        #expect(identity.serverFields == nil)
        let body = String(decoding: server.captured.last!.httpBody!, as: UTF8.self)
        #expect(body.contains("name=\"front\"") && body.contains("name=\"back\"") && body.contains(qr))
    }

    @Test func editsPersistAndOnlyEditedValuesAreConfirmed() async throws {
        let server = MockServer()
        let identity = try await verified(server)
        identity.acceptPhoto(IDCardPhoto(jpeg: Data([1]), sharpness: 100, glareFraction: 0, qr: nil), isBack: false)
        identity.acceptPhoto(IDCardPhoto(jpeg: Data([2]), sharpness: 100, glareFraction: 0, qr: qr), isBack: true)
        server.enqueue("{\"status\":\"ok\",\"fields\":{\"full_name\":\"Nguyễn Văn Mẫu\",\"id_number\":\"000000000001\",\"date_of_birth\":\"1995-01-01\",\"sex\":\"Nam\",\"address\":\"Địa chỉ mẫu\",\"issued_on\":\"2021-01-01\"}}")
        #expect(await identity.uploadCard() == .confirm)
        #expect(identity.draftValues[0] == "NGUYỄN VĂN MẪU")
        #expect(identity.draftValues[1] == "000 000 000 001")
        #expect(identity.draftValues[2] == "01/01/1995")
        identity.draftValues[0] = "Nguyễn Văn Mẫu B"
        identity.draftValues[1] = "999999999999" // Model must keep the server ID locked, too.
        identity.draftValues[2] = "02/01/1995"
        let edited = try #require(identity.confirmedFields)
        #expect(edited.idNumber == "000000000001")
        #expect(edited.dateOfBirth == "1995-01-02")
        server.drop()
        #expect(await identity.confirmCard() == nil)
        #expect(identity.draftValues[0] == "Nguyễn Văn Mẫu B")
        #expect(identity.draftValues[2] == "02/01/1995")
        server.enqueue("{\"received\":true}")
        #expect(await identity.confirmCard() == .faceReady)
        let sent = try SessionJSON.decoder().decode(IdCardFields.self, from: server.captured.last!.httpBody!)
        #expect(sent == edited)
        #expect(sent.issuedOn == "2021-01-01")
        #expect(identity.serverFields == edited)
    }

    @Test func invalidLocalImagesNeverAdvance() async throws {
        let server = MockServer()
        let identity = try await verified(server)
        let before = server.captured.count
        #expect(await identity.uploadCard() == .idFront)
        identity.acceptPhoto(IDCardPhoto(jpeg: Data([1]), sharpness: 1, glareFraction: 0, qr: nil), isBack: false)
        #expect(await identity.uploadCard() == .idFront)
        identity.acceptPhoto(IDCardPhoto(jpeg: Data([1]), sharpness: 100, glareFraction: 0, qr: nil), isBack: false)
        identity.acceptPhoto(IDCardPhoto(jpeg: Data([2]), sharpness: 100, glareFraction: 0, qr: "not a CCCD QR"), isBack: true)
        #expect(await identity.uploadCard() == .idBack)
        #expect(server.captured.count == before)
        identity.reset()
        #expect(identity.frontPhoto == nil && identity.backPhoto == nil && identity.draftValues.isEmpty)
    }

    @Test func QRRetakePopsBackToTheExistingBackCaptureRoute() {
        let navigation = AppNavigation()
        navigation.path = [.auth, .phone, .otp, .idFront, .idFrontReview, .idBack, .idBackReview]
        navigation.returnTo(.idBack)
        #expect(navigation.path == [.auth, .phone, .otp, .idFront, .idFrontReview, .idBack])
        navigation.returnTo(.idBack)
        #expect(navigation.path.count == 6)
        navigation.returnTo(.idFront)
        #expect(navigation.path == [.auth, .phone, .otp, .idFront])
    }
}
