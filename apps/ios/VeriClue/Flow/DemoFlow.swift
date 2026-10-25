import Combine
import Foundation

enum Purpose: String, CaseIterable, Identifiable {
    case onboarding
    case reauth
    case recovery

    var id: String { rawValue }

    var label: String {
        switch self {
        case .onboarding: "Đăng ký"
        case .reauth: "Đăng nhập lại"
        case .recovery: "Khôi phục"
        }
    }
}

enum DemoOutcome: String, CaseIterable, Identifiable {
    case pass
    case review
    case retryQuality = "retry_quality"
    case retryChallenge = "retry_challenge"
    case voiceAgain = "voice_again"

    var id: String { rawValue }

    var label: String {
        switch self {
        case .pass: "Đạt"
        case .review: "Chờ duyệt"
        case .retryQuality: "Chụp lại (chất lượng)"
        case .retryChallenge: "Làm lại thử thách"
        case .voiceAgain: "Đọc lại câu"
        }
    }

    var destination: Route {
        switch self {
        case .pass: .success
        case .review: .review
        case .retryQuality: .retryQuality
        case .retryChallenge: .retryChallenge
        case .voiceAgain: .voiceAgain
        }
    }
}

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

    let mockScenarios = ["genuine", "low_quality", "print", "replay", "virtual_cam", "faceswap", "voice_clone", "error"]

    func afterOTP() -> Route {
        purpose == .reauth ? .faceReady : .idFront
    }

    func afterHeadTurn() -> Route {
        purpose == .reauth ? .uploading : .voice
    }

    func routeSequence(for purpose: Purpose) -> [Route] {
        let start: [Route]
        switch purpose {
        case .onboarding:
            start = [.auth, .terms, .consent, .intro, .permission, .phone, .otp, .idFront, .idFrontReview, .idBack, .idBackReview, .confirm]
        case .reauth:
            start = [.auth, .phone, .otp]
        case .recovery:
            start = [.auth, .phone, .otp, .idFront, .idFrontReview, .idBack, .idBackReview, .confirm]
        }
        let face: [Route] = [.faceReady, .framing, .holdStill, .turnHead]
        let voice: [Route] = purpose == .reauth ? [] : [.voice]
        return start + face + voice + [.uploading, .checking, .success]
    }

    func resetForBank() {
        previewMode = false
        purpose = .onboarding
        outcome = .pass
    }
}
