import Foundation
import Testing
@testable import VeriClue

@MainActor
struct CompactStartTests {
    @Test func consentStartsEmptyAndNeedsReadingAgreementAndRequiredChoices() {
        var agreement = Agreement()
        let empty: Set<Int> = []
        #expect(!agreement.canContinue(selected: empty, required: ConsentPolicy.requiredIDs))
        #expect(ConsentPolicy.requiredIDs == [0]) // Android demo policy, not legal approval.
        agreement.toggle()
        #expect(!agreement.accepted)
        agreement.reachedEnd()
        #expect(!agreement.canContinue(selected: [0, 1, 2], required: ConsentPolicy.requiredIDs))
        agreement.toggle()
        #expect(!agreement.canContinue(selected: [1, 2], required: ConsentPolicy.requiredIDs))
        #expect(agreement.canContinue(selected: [0], required: ConsentPolicy.requiredIDs))
        agreement.toggle()
        #expect(!agreement.canContinue(selected: [0], required: ConsentPolicy.requiredIDs))
    }

    @Test func legacyRoutesCannotAppearAndRecoveryHasNoCard() {
        let demo = DemoFlow()
        for purpose in Purpose.allCases {
            let routes = demo.routeSequence(for: purpose)
            #expect(!routes.contains { ["consent", "intro", "permission"].contains($0.rawValue) })
            if purpose != .onboarding {
                #expect(!routes.contains(.idFront) && !routes.contains(.idBack) && !routes.contains(.confirm))
            }
        }
        let registration = demo.routeSequence(for: .onboarding)
        let terms = registration.firstIndex(of: .terms)!
        #expect(registration[terms + 1] == .phone)
    }

    @Test func onlyUnambiguousSixASCIIDigitsAreAutofilled() {
        #expect(OtpRules.simulatedCode(in: "Mã xác nhận: 654321. Hạn 2 phút.") == "654321")
        for invalid: String? in [nil, "", "12345", "1234567", "１２３４５６", "١٢٣٤٥٦", "123456 hoặc 654321", "١123456"] {
            #expect(OtpRules.simulatedCode(in: invalid) == nil)
        }
    }

    @Test func autoFillDoesNotVerifyAndManualEditsSurviveReturningToPhone() async throws {
        let server = MockServer()
        let identity = IdentityFlow(api: server.api())
        identity.begin(purpose: .recovery, scenario: "genuine")
        identity.phone = "0912345678"
        server.enqueue(try Fixtures.session())
        server.enqueue("{\"expires_at\":\"2100-01-01T00:00:00Z\",\"attempts_left\":5,\"simulated_sms\":\"Mã 654321\"}")
        #expect(await identity.sendOTP() == .otp)
        #expect(identity.code == "654321" && !identity.otpVerified)
        #expect(server.captured.count == 2)
        identity.eraseCode(); identity.appendCode("0")
        #expect(identity.code == "654320")
        #expect(await identity.sendOTP() == .otp)
        #expect(identity.code == "654320" && server.captured.count == 2)
        server.enqueue("{\"status\":\"pass\",\"attempts_left\":4}")
        #expect(await identity.verifyOTP() == .faceReady)
        #expect(identity.attemptsLeft == 4 && identity.otpVerified)
    }
}
