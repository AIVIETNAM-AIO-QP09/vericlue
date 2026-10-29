enum Purpose: String, CaseIterable, Identifiable, Sendable {
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
