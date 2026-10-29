import Combine
import Foundation

struct OTPResendClock {
    private(set) var deadline: Date?

    mutating func sent(at now: Date = Date()) { deadline = now.addingTimeInterval(45) }
    func remaining(at now: Date = Date()) -> Int {
        guard let deadline else { return 0 }
        return max(0, Int(ceil(deadline.timeIntervalSince(now))))
    }
}

@MainActor
final class IdentityFlow: ObservableObject {
    private let api: SessionApi?
    private let accountFlow: AccountFlow
    private var accountEntry: AccountEntry?
    @Published private(set) var accountHint: String?
    private var live: LiveFlow?
    private var generation = 0
    private var purpose = Purpose.onboarding
    private var scenario: String?
    private var sessionPhone: String?
    @Published private(set) var otpVerified = false
    var liveFlow: LiveFlow? { live } // IOS-04 must reuse this session/token after stage A.

    @Published var phone = ""
    @Published var code = ""
    @Published private(set) var busy = false
    @Published private(set) var errorText: String?
    @Published private(set) var otpSMS: String?
    @Published private(set) var attemptsLeft: Int?
    @Published private(set) var otpHasError = false
    @Published private(set) var otpLocked = false
    @Published private(set) var resendClock = OTPResendClock()
    @Published private(set) var frontPhoto: IDCardPhoto?
    @Published private(set) var backPhoto: IDCardPhoto?
    @Published private(set) var cardQRRejected = false
    var cardQR: String? { CCCDQR.select(front: frontPhoto?.qr, back: backPhoto?.qr) }
    @Published private(set) var serverFields: IdCardFields?
    @Published private(set) var awaitingFaceConfirmation = false
    @Published private(set) var frontCaptureID = UUID()
    @Published private(set) var backCaptureID = UUID()
    @Published var draftValues: [String] = []
    private var originallyShown: [String] = []

    init(api: SessionApi? = nil, accountFlow: AccountFlow? = nil) {
        self.api = api ?? Self.configuredAPI()
        self.accountFlow = accountFlow ?? AccountFlow()
        live = self.api.map { LiveFlow(api: $0) }
    }

    private static func configuredAPI() -> SessionApi? {
        guard let url = APIEndpointPolicy.baseURL(
            Bundle.main.object(forInfoDictionaryKey: "API_BASE_URL") as? String,
            requiresHTTPS: APIEndpointPolicy.requiresHTTPS) else { return nil }
        return SessionApi(baseURL: url)
    }

    func begin(purpose: Purpose, scenario: String?) {
        reset()
        self.purpose = purpose
        self.scenario = scenario
    }

    func beginAccount(purpose: Purpose, scenario: String?, signingEnabled: Bool = SigningConfiguration.enabled) async -> AccountEntry? {
        guard !busy else { return nil }
        reset()
        let current = generation
        busy = true
        defer { if current == generation { busy = false } }
        guard let api else { errorText = "Ứng dụng chưa được cấu hình địa chỉ máy chủ hợp lệ."; return nil }
        do {
            let entry = try await accountFlow.begin(purpose, signingEnabled: signingEnabled)
            guard current == generation, !Task.isCancelled else { return nil }
            self.purpose = entry.purpose; self.scenario = scenario
            accountEntry = entry; accountHint = entry.hint
            live = LiveFlow(api: api, accountEntry: entry, accountFlow: accountFlow)
            return entry
        } catch {
            if current == generation, !Task.isCancelled { errorText = "Chưa thể mở thông tin thiết bị. Vui lòng thử lại sau." }
            return nil
        }
    }

    func reset() {
        generation += 1
        live?.reset()
        accountEntry = nil; accountHint = nil
        live = api.map { LiveFlow(api: $0) }
        phone = ""
        sessionPhone = nil
        code = ""
        busy = false
        errorText = nil
        otpSMS = nil
        attemptsLeft = nil
        otpHasError = false
        otpLocked = false
        otpVerified = false
        resendClock = OTPResendClock()
        clearPhotos()
    }

    func cancelPendingRequests() {
        generation += 1
        busy = false
        live?.cancelPendingRequests()
    }

    func appendPhone(_ digit: Character) {
        guard !busy else { return }
        phone = PhoneRules.append(phone, digit)
    }

    func appendCode(_ digit: Character) {
        guard !busy, !otpLocked, !otpVerified else { return }
        if otpHasError { code = ""; otpHasError = false; errorText = nil }
        code = OtpRules.append(code, digit)
    }

    func replaceCode(_ value: String) {
        guard !busy, !otpLocked, !otpVerified, OtpRules.acceptsInput(value), value != code else { return }
        code = value
        otpHasError = false
        errorText = nil
    }

    func eraseCode() {
        guard !busy, !otpVerified else { return }
        if !code.isEmpty { code.removeLast() }
        if !otpLocked { otpHasError = false; errorText = nil }
    }

    func sendOTP(resend: Bool = false, now: Date = Date()) async -> Route? {
        guard !busy, PhoneRules.isValid(phone) else { return nil }
        if sessionPhone == phone && otpVerified { return .otp }
        if sessionPhone == phone && attemptsLeft == 0 {
            errorText = FlowRules.otpErrorText("otp_locked")
            return nil
        }
        if resend && resendClock.remaining(at: now) > 0 { return nil }
        if sessionPhone == phone && resendClock.remaining(at: now) > 0 { return .otp }
        if let sessionPhone, sessionPhone != phone {
            live?.reset()
            live = api.map { LiveFlow(api: $0, accountEntry: accountEntry, accountFlow: accountFlow) }
            otpVerified = false
            otpSMS = nil
            code = ""
            attemptsLeft = nil
            otpHasError = false
            otpLocked = false
            resendClock = OTPResendClock()
            clearPhotos()
        }
        guard let live else {
            errorText = "Ứng dụng chưa được cấu hình địa chỉ máy chủ hợp lệ. Vui lòng liên hệ nhóm demo."
            return nil
        }
        sessionPhone = phone
        let current = generation
        busy = true
        errorText = nil
        defer { if current == generation { busy = false } }
        let error = await live.sendOtp(phone: phone, purpose: purpose, scenario: scenario)
        guard current == generation, !Task.isCancelled else { return nil }
        if let error { return handle(error, otp: true) }
        otpSMS = live.otpSms
        attemptsLeft = live.attemptsLeft
        code = OtpRules.simulatedCode(in: otpSMS) ?? ""
        otpHasError = false
        otpLocked = live.attemptsLeft == 0
        resendClock.sent() // Start from acceptance, not the time the network request began.
        return .otp
    }

    func verifyOTP() async -> Route? {
        guard !otpVerified, !busy, !otpHasError, !otpLocked, OtpRules.isComplete(code) else { return nil }
        guard let live else { return .errorService }
        let current = generation
        busy = true
        errorText = nil
        defer { if current == generation { busy = false } }
        let result = await live.verifyOtp(code: code)
        guard current == generation, !Task.isCancelled else { return nil }
        attemptsLeft = live.attemptsLeft
        switch result {
        case .pass:
            otpVerified = true
            return FlowRules.afterOtp(purpose)
        case .wrong(let remaining):
            otpHasError = true
            otpLocked = remaining <= 0
            errorText = FlowRules.otpWrongText(remaining)
            return nil
        case .fail(let error): return handle(error, otp: true)
        }
    }

    func continueAfterVerifiedOTP() -> Route? {
        guard !busy, otpVerified, phone == sessionPhone else { return nil }
        return FlowRules.afterOtp(purpose)
    }

    func acceptPhoto(_ photo: IDCardPhoto, isBack: Bool) {
        guard !busy else { return }
        errorText = nil
        cardQRRejected = false
        serverFields = nil
        originallyShown = []
        draftValues = []
        awaitingFaceConfirmation = false
        if isBack { backPhoto = photo }
        else { frontPhoto = photo }
    }

    func retake(isBack: Bool) {
        guard !busy else { return }
        if isBack { backPhoto = nil; backCaptureID = UUID() }
        else { frontPhoto = nil; frontCaptureID = UUID() }
        serverFields = nil; originallyShown = []; draftValues = []
        awaitingFaceConfirmation = false
        cardQRRejected = false
        errorText = nil
    }

    func clearPhotos() {
        cardQRRejected = false
        frontPhoto = nil
        backPhoto = nil
        frontCaptureID = UUID(); backCaptureID = UUID()
        serverFields = nil
        originallyShown = []
        draftValues = []
        awaitingFaceConfirmation = false
    }

    func uploadCard() async -> Route? {
        guard !busy, otpVerified else { return nil }
        guard let front = frontPhoto, !front.jpeg.isEmpty, front.canContinue(isBack: false) else {
            errorText = "Hãy chụp lại mặt trước CCCD rõ nét, không bị lóa."
            return .idFront
        }
        guard let back = backPhoto, !back.jpeg.isEmpty, back.canContinue(isBack: true) else {
            errorText = "Hãy chụp lại mặt sau CCCD rõ nét, không bị lóa."
            return .idBack
        }
        guard let qr = cardQR, !cardQRRejected else {
            errorText = "Chưa đọc được mã QR trên thẻ. Hãy chọn chụp lại mặt chứa mã QR."
            return .idReview
        }
        if awaitingFaceConfirmation && serverFields != nil { return .faceReady }
        guard let live else { return .errorService }
        let current = generation
        busy = true
        errorText = nil
        defer { if current == generation { busy = false } }
        let result = await live.sendIdCard(front: front.jpeg, back: back.jpeg, qr: qr)
        guard current == generation, !Task.isCancelled else { return nil }
        switch result {
        case .accepted:
            guard let fields = live.idFields else { return .errorService }
            serverFields = fields
            originallyShown = Self.displayValues(fields)
            draftValues = originallyShown
            awaitingFaceConfirmation = true
            return .faceReady
        case .retry:
            cardQRRejected = true
            serverFields = nil; originallyShown = []; draftValues = []
            awaitingFaceConfirmation = false
            errorText = "Chưa đọc được mã QR trên thẻ. Hãy chọn chụp lại mặt chứa mã QR."
            return .idReview
        case .fail(let error): return handle(error)
        }
    }

    var confirmedFields: IdCardFields? {
        guard let serverFields, draftValues.count == 5 else { return nil }
        return FlowRules.confirmedFields(server: serverFields, shown: originallyShown, edited: draftValues)
    }

    var draftError: String? {
        guard serverFields != nil, draftValues.count == 5, originallyShown.count == 5 else {
            return "Dịch vụ chưa phản hồi. Vui lòng thử lại sau."
        }
        if draftValues[0].trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { return "Hãy nhập họ và tên." }
        if draftValues[2] != originallyShown[2], FlowRules.displayToIso(draftValues[2]) == nil {
            return "Ngày sinh chưa hợp lệ. Hãy nhập theo dạng dd/MM/yyyy."
        }
        if draftValues[3] != originallyShown[3], !["Nam", "Nữ"].contains(draftValues[3]) {
            return "Hãy chọn giới tính Nam hoặc Nữ."
        }
        return nil
    }

    func confirmCard() async -> Route? {
        guard !busy else { return nil }
        if live?.idCardConfirmed == true && !awaitingFaceConfirmation { return .uploading }
        if let draftError { errorText = draftError; return nil }
        guard let live, let fields = confirmedFields else { return .errorService }
        let current = generation
        busy = true
        errorText = nil
        defer { if current == generation { busy = false } }
        let error = await live.confirmIdCard(fields: fields)
        guard current == generation, !Task.isCancelled else { return nil }
        if let error { return handle(error) }
        serverFields = fields
        originallyShown = Self.displayValues(fields)
        draftValues = originallyShown
        awaitingFaceConfirmation = false
        return .uploading
    }

    private func handle(_ error: ApiError, otp: Bool = false) -> Route? {
        switch error {
        case .network:
            errorText = "Không kết nối được. Hãy kiểm tra kết nối mạng rồi thử lại. Các bước bạn đã làm vẫn được giữ."
        case .unauthorized, .expired: return .errorSession
        case .conflict(let code):
            if !otp && (code?.hasPrefix("otp_") == true) { return .errorService }
            switch code {
            case "recovery_required": return .recoveryRequired
            case "otp_already_verified": otpVerified = true; return .otp
            case "otp_expired", "otp_locked":
                otpHasError = true
                otpLocked = true
                if code == "otp_locked" { attemptsLeft = 0 }
                errorText = FlowRules.otpErrorText(code)
            case "otp_too_many": return .errorService
            case "session_closed", "session_too_long": return .errorSession
            case "challenge_expired", "challenge_mismatch": return .faceExpired
            default: return .errorService
            }
        case .busy, .badResponse, .server: return .errorService
        }
        return nil
    }

    static func displayValues(_ fields: IdCardFields) -> [String] {
        let id = fields.idNumber ?? ""
        var groups: [String] = []
        var start = id.startIndex
        while start < id.endIndex {
            let end = id.index(start, offsetBy: min(3, id.distance(from: start, to: id.endIndex)))
            groups.append(String(id[start..<end]))
            start = end
        }
        return [(fields.fullName ?? "").uppercased(), groups.joined(separator: " "),
                FlowRules.isoToDisplay(fields.dateOfBirth), fields.sex ?? "", fields.address ?? ""]
    }
}
