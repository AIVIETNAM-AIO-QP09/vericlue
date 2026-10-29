import Foundation
import Testing
@testable import VeriClue

@MainActor
struct UXParityTests {
    @Test func systemOTPInputAcceptsOnlyUpToSixASCIIDigits() {
        for value in ["", "0", "012345", "654321"] { #expect(OtpRules.acceptsInput(value)) }
        for value in ["1234567", "１２３４５６", "١٢٣٤٥٦", "12 3456", "12345a", "123456\n"] {
            #expect(!OtpRules.acceptsInput(value))
        }
    }

    @Test func systemFillDoesNotVerifyResetBudgetOrEditVerifiedCode() async throws {
        let server = MockServer(), identity = IdentityFlow(api: server.api())
        identity.begin(purpose: .onboarding, scenario: "genuine")
        identity.phone = "0912345678"
        server.enqueue(try Fixtures.session())
        server.enqueue("{\"expires_at\":\"2099-01-01T00:00:00Z\",\"attempts_left\":5,\"simulated_sms\":\"Mã 654321\"}")
        #expect(await identity.sendOTP() == .otp)
        identity.replaceCode("111111")
        #expect(!identity.otpVerified && server.captured.count == 2)
        server.enqueue("{\"status\":\"retry\",\"attempts_left\":4}")
        #expect(await identity.verifyOTP() == nil)
        #expect(identity.otpHasError && identity.attemptsLeft == 4)
        identity.replaceCode("１２３４５６")
        #expect(identity.code == "111111" && identity.otpHasError)
        identity.replaceCode("654321")
        #expect(identity.code == "654321" && !identity.otpHasError && identity.attemptsLeft == 4)
        #expect(server.captured.count == 3 && !identity.otpVerified)
        server.enqueue("{\"status\":\"pass\",\"attempts_left\":4}")
        #expect(await identity.verifyOTP() == .idFront)
        identity.replaceCode("000000")
        #expect(identity.code == "654321" && identity.otpVerified && server.captured.count == 4)
    }

    @Test func completionFeedbackFiresOncePerEventAndResetsForRetake() {
        var gate = CompletionFeedbackGate()
        let events = [
            gate.consume(completed: false, event: "front"),
            gate.consume(completed: true, event: "front"),
            gate.consume(completed: true, event: "front"),
            gate.consume(completed: true, event: "back"),
            gate.consume(completed: false, event: "back"),
            gate.consume(completed: true, event: "back"),
            gate.consume(completed: true, event: "back")
        ]
        #expect(events == [false, true, false, true, false, true, false])
    }
}
