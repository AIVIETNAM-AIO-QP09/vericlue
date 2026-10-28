import Combine
import Foundation

@MainActor
final class DemoFlow: ObservableObject {
    @Published var purpose: Purpose = .onboarding
    @Published var outcome: DemoOutcome = .pass
    @Published var mockScenario = "genuine"
    #if DEBUG
    @Published var useLiveAPI = false
    #else
    @Published var useLiveAPI = true
    #endif
    @Published var previewMode = false
    @Published var idConfirmed = false

    let mockScenarios = ["genuine", "low_quality", "print", "replay", "virtual_cam", "faceswap", "voice_clone", "error"]

    func afterOTP() -> Route {
        FlowRules.afterOtp(purpose)
    }

    func afterHeadTurn() -> Route {
        if purpose == .onboarding && !idConfirmed { return .confirm }
        return afterConfirmation()
    }

    func confirmIdentity() -> Route {
        idConfirmed = true
        return afterConfirmation()
    }

    private func afterConfirmation() -> Route {
        purpose == .reauth ? .uploading : .voice
    }

    func routeSequence(for purpose: Purpose) -> [Route] {
        let start: [Route]
        switch purpose {
        case .onboarding:
            start = [.auth, .terms, .phone, .otp, .idFront, .idBack, .idReview]
        case .reauth:
            start = [.auth, .phone, .otp]
        case .recovery:
            start = [.auth, .phone, .otp]
        }
        let face: [Route] = [.faceReady, .framing, .holdStill, .turnHead]
        let voice: [Route] = purpose == .reauth ? [] : [.voice]
        return start + face + (purpose == .onboarding ? [.confirm] : []) + voice + [.uploading, .checking, .success]
    }

    func resetForBank() {
        previewMode = false
        idConfirmed = false
        purpose = .onboarding
        outcome = .pass
    }
}
