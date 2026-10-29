import Foundation
import Testing
@testable import VeriClue

@MainActor
struct IDAutoCaptureTests {
    private func expectOffer(_ auto: inout IDAutoCapture, good: Bool, at time: Double, equals expected: Bool) {
        let result = auto.offer(good: good, at: time)
        #expect(result == expected, "sample time: \(time)")
    }

    private func expectClaim(_ auto: inout IDAutoCapture, equals expected: Bool) {
        let result = auto.claim()
        #expect(result == expected)
    }

    @Test func initialDelaySamplingAndTwoConsecutiveSamples() {
        var auto = IDAutoCapture()
        auto.begin(at: 10)
        expectOffer(&auto, good: true, at: 11.49, equals: false)
        #expect(auto.consecutive == 0)
        expectOffer(&auto, good: true, at: 11.5, equals: false)
        expectOffer(&auto, good: true, at: 11.9, equals: false)
        #expect(auto.consecutive == 1)
        expectOffer(&auto, good: true, at: 12, equals: true)
        expectClaim(&auto, equals: true)
        expectClaim(&auto, equals: false) // Manual and auto share one shutter lease.
        expectOffer(&auto, good: true, at: 12.5, equals: false)
    }

    @Test func badSampleAndLongGapResetAndCancelRejectsLateSamples() {
        var auto = IDAutoCapture()
        auto.begin(at: 0)
        expectOffer(&auto, good: true, at: 1.5, equals: false)
        expectOffer(&auto, good: false, at: 2, equals: false)
        #expect(auto.consecutive == 0)
        expectOffer(&auto, good: true, at: 2.5, equals: false)
        expectOffer(&auto, good: true, at: 5, equals: false) // Old frame cannot pair with a late one.
        auto.cancel()
        expectClaim(&auto, equals: false)
        expectOffer(&auto, good: true, at: 6, equals: false)
        auto.begin(at: 6)
        expectOffer(&auto, good: true, at: 7.5, equals: false)
        expectOffer(&auto, good: true, at: 8, equals: true)
    }

    @Test func manualShotCanClaimBeforeAutoAndOnlyOnce() {
        var auto = IDAutoCapture()
        expectClaim(&auto, equals: false)
        auto.begin(at: 0)
        expectClaim(&auto, equals: true)
        expectClaim(&auto, equals: false)
        expectOffer(&auto, good: true, at: 2, equals: false)
        auto.cancel(); auto.begin(at: 3)
        expectClaim(&auto, equals: true)
    }

    @Test func sharpRoomIsNotACardAndNeitherSideRequiresItsOwnQR() {
        #expect(!CardText.looksLikeCard("Room 24, bàn ghế và ánh sáng"))
        for text in ["CĂN CƯỚC CÔNG DÂN", "QUỐC TỊCH", "NGÀY CẤP", "CITIZEN IDENTITY", "SOCIALIST\nREPUBLIC"] {
            #expect(CardText.looksLikeCard(text))
        }
        let room = IDCardObservation(sharpness: 500, glareFraction: 0, looksLikeCard: false, hasQR: false, sampledAt: 0)
        #expect(!room.good(isBack: false))
        let front = IDCardObservation(sharpness: 100, glareFraction: 0, looksLikeCard: true, hasQR: false, sampledAt: 0)
        #expect(front.good(isBack: false) && front.good(isBack: true))
        let glare = IDCardObservation(sharpness: 100, glareFraction: 0.1, looksLikeCard: true, hasQR: true, sampledAt: 0)
        #expect(!glare.good(isBack: true))
    }

    @Test func retakingEitherSideKeepsOtherSideAndInvalidatesOldFields() {
        let identity = IdentityFlow(api: MockServer().api())
        let front = IDCardPhoto(jpeg: Data([1]), sharpness: 100, glareFraction: 0, qr: nil)
        let back = IDCardPhoto(jpeg: Data([2]), sharpness: 100, glareFraction: 0,
            qr: "000000000001||DEMO|01011995|Nam|DEMO")
        identity.acceptPhoto(front, isBack: false); identity.acceptPhoto(back, isBack: true)
        let originalFrontID = identity.frontCaptureID
        let originalBackID = identity.backCaptureID
        identity.retake(isBack: false)
        #expect(identity.frontPhoto == nil && identity.backPhoto?.jpeg == back.jpeg)
        #expect(identity.frontCaptureID != originalFrontID && identity.backCaptureID == originalBackID)
        identity.acceptPhoto(front, isBack: false)
        #expect(identity.backPhoto?.jpeg == back.jpeg)
        identity.retake(isBack: true)
        #expect(identity.backCaptureID != originalBackID)
        #expect(identity.frontPhoto?.jpeg == front.jpeg && identity.backPhoto == nil)
        #expect(identity.serverFields == nil && identity.draftValues.isEmpty && !identity.awaitingFaceConfirmation)
    }
}
