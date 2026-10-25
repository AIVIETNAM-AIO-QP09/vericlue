import Testing
@testable import VeriClue

@MainActor
struct FlowRulesTests {
    @Test func routesStagesAndErrorScreens() {
        #expect(FlowRules.afterOtp(.reauth) == .faceReady)
        #expect(FlowRules.afterTurnHead(.reauth) == .checking)
        for purpose in [Purpose.onboarding, .recovery] {
            #expect(FlowRules.afterOtp(purpose) == .idFront)
            #expect(FlowRules.afterTurnHead(purpose) == .voice)
        }
        #expect(Set(DemoOutcome.allCases.map(FlowRules.afterChecking)).count == DemoOutcome.allCases.count)
        #expect(FlowRules.stepOf(.otp) == 1)
        #expect(FlowRules.stepOf(.holdStill) == 2)
        #expect(FlowRules.stepOf(.voice) == 3)
        #expect(FlowRules.stepOf(.success) == nil)
        #expect(FlowRules.resumeRedoesFace(.holdStill))
        #expect(FlowRules.resumeRedoesFace(.voice))
        for route in [Route.uploading, .idFront] { #expect(!FlowRules.resumeRedoesFace(route)) }
        #expect(!FlowRules.resumeRedoesFace(nil))
        #expect(FlowRules.afterNetworkRetry(live: true) == .uploading)
        #expect(FlowRules.afterNetworkRetry(live: false) == .checking)
        #expect(FlowRules.checkedByServer(voiceChecked: false) == ["Khuôn mặt"])
        #expect(FlowRules.checkedByServer(voiceChecked: true) == ["Khuôn mặt", "Giọng nói"])
        for error in [ApiError.network, .unauthorized, .expired, .busy, .badResponse, .server, .conflict(code: nil)] {
            #expect(FlowRules.errorRoute(error) != .success)
        }
    }

    @Test func statusIsFailClosedAndContextSpecific() {
        #expect(FlowRules.routeForStatus("pass") == .success)
        #expect(FlowRules.routeForStatus("retry") == .retryChallenge)
        #expect(FlowRules.routeForStatus("retry", retryHint: "MORE_LIGHT") == .retryQuality)
        #expect(FlowRules.routeForStatus("voice_challenge") == .voice)
        #expect(FlowRules.routeForStatus("voice_challenge", inVoiceStep: true) == .voiceAgain)
        #expect(FlowRules.routeForStatus("deny") == .deny)
        #expect(FlowRules.routeForStatus("recovery_required") == .recoveryRequired)
        #expect(FlowRules.routeForStatus("retry", inVoiceStep: true) == nil)
        #expect(FlowRules.routeForStatus("recovery_required", inVoiceStep: true) == nil)
        for status in ["degraded", "error", "unknown", "", "PASS"] { #expect(FlowRules.routeForStatus(status) == nil) }
    }

    @Test func digitInputAndAgreement() {
        let phone = "09a0000000099".reduce("") { PhoneRules.append($0, $1) }
        #expect(phone == "0900000000")
        #expect(PhoneRules.isValid(phone))
        #expect(!PhoneRules.isValid("1900000000"))
        #expect(!PhoneRules.isValid("09abcdefgh"))
        #expect(PhoneRules.format(phone) == "0900 000 000")
        let otp = "1234567".reduce("") { OtpRules.append($0, $1) }
        #expect(otp == "123456" && OtpRules.isComplete(otp))
        #expect(!OtpRules.isComplete("abcdef"))
        var agreement = Agreement()
        agreement.toggle()
        #expect(!agreement.accepted && !agreement.canContinue)
        agreement.reachedEnd()
        agreement.toggle()
        #expect(agreement.canContinue)
        agreement.toggle()
        #expect(!agreement.canContinue)
    }

    @Test func onlyActualValidEditsDifferFromQR() {
        let server = IdCardFields(fullName: "Nguyễn Văn An", idNumber: "001099012345", dateOfBirth: "1995-01-01", sex: "Nam", address: "12 Phố Huế", issuedOn: "2021-06-15")
        let shown = ["NGUYỄN VĂN AN", "001 099 012 345", "01/01/1995", "Nam", "12 Phố Huế"]
        #expect(FlowRules.confirmedFields(server: server, shown: shown, edited: shown) == server)
        var edited = shown
        edited[1] = "999999999999"
        edited[2] = "02/01/1995"
        edited[4] = "14 Phố Huế"
        let out = FlowRules.confirmedFields(server: server, shown: shown, edited: edited)
        #expect(out.dateOfBirth == "1995-01-02" && out.address == "14 Phố Huế")
        #expect(out.fullName == server.fullName && out.idNumber == server.idNumber && out.issuedOn == server.issuedOn)
        edited[2] = "31/02/1995"
        edited[3] = "invalid"
        let invalid = FlowRules.confirmedFields(server: server, shown: shown, edited: edited)
        #expect(invalid.dateOfBirth == server.dateOfBirth && invalid.sex == server.sex)
        #expect(FlowRules.confirmedFields(server: server, shown: [], edited: []) == server)
        #expect(FlowRules.isoToDisplay("1995-01-01") == "01/01/1995")
        #expect(FlowRules.displayToIso("2/1/1995") == "1995-01-02")
        #expect(FlowRules.displayToIso("29/02/2024") == "2024-02-29")
        #expect(FlowRules.displayToIso("29/02/2023") == nil)
    }

    @Test func qualityAndOTPTextsMatchAndroid() {
        #expect(FlowRules.otpWrongText(3) == "Mã chưa đúng. Bạn còn 3 lần thử.")
        #expect(FlowRules.otpWrongText(0) == "Bạn đã nhập sai quá số lần. Hãy bấm \"Gửi lại mã\".")
        #expect(FlowRules.otpErrorText("otp_expired") == "Mã đã hết hạn. Hãy bấm \"Gửi lại mã\".")
        #expect(FlowRules.otpErrorText("otp_locked") == FlowRules.otpWrongText(0))
        #expect(FlowRules.otpErrorText("session_closed") == nil)
        let hints = ["MORE_LIGHT": "Ra chỗ sáng hơn", "MOVE_CLOSER": "Lại gần hơn", "MOVE_BACK": "Lùi ra xa hơn một chút", "FACE_CENTER": "Đưa khuôn mặt vào giữa khung hình", "HOLD_STILL": "Giữ yên điện thoại và khuôn mặt", "QUIET_PLACE": "Chuyển đến nơi yên tĩnh hơn", "BRIGHTNESS_UP": "Tăng độ sáng màn hình"]
        for (hint, text) in hints { #expect(FlowRules.retryHintText(hint) == text) }
    }
}
