import Foundation

enum FlowRules {
    static func afterOtp(_ purpose: Purpose) -> Route { purpose == .reauth ? .faceReady : .idFront }
    static func afterTurnHead(_ purpose: Purpose) -> Route { purpose == .reauth ? .checking : .voice }
    static func afterChecking(_ outcome: DemoOutcome) -> Route { outcome.destination }

    static func routeForStatus(_ status: String, retryHint: String? = nil, inVoiceStep: Bool = false) -> Route? {
        switch status {
        case "pass": .success
        case "review": .review
        case "retry" where !inVoiceStep: retryHint == nil ? .retryChallenge : .retryQuality
        case "voice_challenge": inVoiceStep ? .voiceAgain : .voice
        case "deny": .deny
        case "recovery_required" where !inVoiceStep: .recoveryRequired
        default: nil
        }
    }

    static func retryHintText(_ hint: String?) -> String {
        switch hint {
        case "MORE_LIGHT": "Ra chỗ sáng hơn"
        case "MOVE_CLOSER": "Lại gần hơn"
        case "MOVE_BACK": "Lùi ra xa hơn một chút"
        case "FACE_CENTER": "Đưa khuôn mặt vào giữa khung hình"
        case "HOLD_STILL": "Giữ yên điện thoại và khuôn mặt"
        case "QUIET_PLACE": "Chuyển đến nơi yên tĩnh hơn"
        case "BRIGHTNESS_UP": "Tăng độ sáng màn hình"
        default: "Hãy ra chỗ sáng hơn và giữ điện thoại ngang tầm mặt."
        }
    }

    static func otpWrongText(_ attemptsLeft: Int) -> String {
        attemptsLeft > 0 ? "Mã chưa đúng. Bạn còn \(attemptsLeft) lần thử." : "Bạn đã nhập sai quá số lần. Hãy bấm \"Gửi lại mã\"."
    }

    static func otpErrorText(_ code: String?) -> String? {
        switch code {
        case "otp_expired": "Mã đã hết hạn. Hãy bấm \"Gửi lại mã\"."
        case "otp_locked": "Bạn đã nhập sai quá số lần. Hãy bấm \"Gửi lại mã\"."
        default: nil
        }
    }

    static func isoToDisplay(_ iso: String?) -> String {
        guard let iso else { return "" }
        let parts = iso.split(separator: "-", omittingEmptySubsequences: false)
        guard parts.count == 3 else { return iso }
        return "\(parts[2])/\(parts[1])/\(parts[0])"
    }

    static func displayToIso(_ shown: String) -> String? {
        let parts = shown.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: "/", omittingEmptySubsequences: false)
        guard parts.count == 3,
              parts.allSatisfy({ !$0.isEmpty && $0.allSatisfy({ $0.isASCII && $0.isNumber }) }),
              let day = Int(parts[0]), let month = Int(parts[1]), let year = Int(parts[2]),
              (1...9999).contains(year), (1...12).contains(month), (1...31).contains(day) else { return nil }
        let calendar = Calendar(identifier: .gregorian)
        let components = DateComponents(year: year, month: month, day: day)
        guard let date = calendar.date(from: components) else { return nil }
        let actual = calendar.dateComponents([.year, .month, .day], from: date)
        guard actual.year == year, actual.month == month, actual.day == day else { return nil }
        func pad(_ number: Int, to length: Int) -> String {
            let text = String(number)
            return String(repeating: "0", count: max(0, length - text.count)) + text
        }
        return "\(pad(year, to: 4))-\(pad(month, to: 2))-\(pad(day, to: 2))"
    }

    static func confirmedFields(server: IdCardFields, shown: [String], edited: [String]) -> IdCardFields {
        func changed(_ index: Int) -> String? {
            guard shown.indices.contains(index), edited.indices.contains(index) else { return nil }
            let value = edited[index].trimmingCharacters(in: .whitespacesAndNewlines)
            return value == shown[index].trimmingCharacters(in: .whitespacesAndNewlines) ? nil : value
        }
        var result = server
        if let value = changed(0) { result.fullName = value }
        // The ID is locked even if a caller tampers with the edit rows.
        if let value = changed(2), let iso = displayToIso(value) { result.dateOfBirth = iso }
        if let value = changed(3), ["Nam", "Nữ"].contains(value) { result.sex = value }
        if let value = changed(4) { result.address = value }
        return result
    }

    static func afterNetworkRetry(live: Bool) -> Route { live ? .uploading : .checking }
    static func checkedByServer(voiceChecked: Bool) -> [String] {
        voiceChecked ? ["Khuôn mặt", "Giọng nói"] : ["Khuôn mặt"]
    }
    static func confirmsCaptureExit(_ route: Route) -> Bool {
        [.faceReady, .framing, .holdStill, .turnHead, .voice, .voiceAgain,
         .uploading, .checking, .retryQuality, .retryChallenge].contains(route)
    }
    static func sessionExpired(_ expiresAt: String, now: Date = Date()) -> Bool {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let fractional = formatter.date(from: expiresAt)
        formatter.formatOptions = [.withInternetDateTime]
        guard let deadline = fractional ?? formatter.date(from: expiresAt) else { return false }
        return now >= deadline // Unknown local date never substitutes for a server decision.
    }
    static func resumeRedoesFace(_ route: Route?) -> Bool { route.map { [2, 3].contains(stepOf($0) ?? 0) } ?? false }
    static func isInterruptedBy(_ route: Route?) -> Bool {
        route.map { [.framing, .holdStill, .turnHead, .voice, .voiceAgain].contains($0) } ?? false
    }
    static func stepOf(_ route: Route) -> Int? {
        switch route {
        case .intro, .permission, .phone, .otp, .otpError, .idFront, .idFrontGlare,
             .idFrontReview, .idBack, .idBackReview, .confirm, .editInfo: 1
        case .faceReady, .framing, .holdStill, .turnHead, .retryQuality, .retryChallenge: 2
        case .voice, .voiceAgain: 3
        default: nil
        }
    }
    static func errorRoute(_ error: ApiError) -> Route {
        switch error {
        case .network: .errorNetwork
        case .unauthorized, .expired: .errorSession
        case .conflict(let code):
            ["session_closed", "session_too_long"].contains(code ?? "") ? .errorSession : .errorService
        case .busy, .badResponse, .server: .errorService
        }
    }
}

enum PhoneRules {
    static func append(_ current: String, _ digit: Character) -> String {
        digit.isASCII && digit.isNumber && current.count < 10 ? current + String(digit) : current
    }
    static func isValid(_ phone: String) -> Bool {
        phone.count == 10 && phone.first == "0" && phone.allSatisfy { $0.isASCII && $0.isNumber }
    }
    static func format(_ phone: String) -> String {
        phone.enumerated().map { ([4, 7].contains($0.offset) ? " " : "") + String($0.element) }.joined()
    }
}
enum OtpRules {
    static func append(_ current: String, _ digit: Character) -> String {
        digit.isASCII && digit.isNumber && current.count < 6 ? current + String(digit) : current
    }
    static func isComplete(_ code: String) -> Bool {
        code.count == 6 && code.allSatisfy { $0.isASCII && $0.isNumber }
    }
}
struct Agreement {
    var readToEnd = false
    var accepted = false
    var canContinue: Bool { readToEnd && accepted }
    mutating func reachedEnd() { readToEnd = true }
    mutating func toggle() { if readToEnd { accepted.toggle() } }
}
