import Combine
import Foundation
import Security

enum Next: Equatable {
    case to(Route), fail(ApiError)
}

@MainActor
final class LiveFlow: ObservableObject {
    private let api: SessionApi
    @Published private(set) var session: CreateSessionResponse?
    @Published private(set) var challenge: Challenge?
    var token: String? { session?.token }
    var frontalJpeg: Data?
    var colorEvents: [ColorEvent] = []
    @Published private(set) var mediaAcked = false
    @Published private(set) var signalsAcked = false
    @Published private(set) var voiceChecked = false
    @Published private(set) var otpSms: String?
    @Published private(set) var idFields: IdCardFields?
    @Published private(set) var voicePrompt: String?
    @Published private(set) var voiceChallengeId: String?
    @Published private(set) var retryHint: String?
    @Published private(set) var attemptsLeft: Int?
    var pendingWav: Data?
    private(set) var pendingFaceVideo: Data?
    private(set) var pendingVoiceVideo: Data?
    var audioOffsetMs: Int?
    private var pendingSignals: Signals?
    private var pendingFaceImage: Data?
    private var voicePayloadPrepared = false
    private var voiceRereads = 0
    private var requestedPurpose: Purpose?
    private var readyRetryChallenge = false
    private var busy = false

    init(api: SessionApi) { self.api = api }

    enum OtpResult: Equatable { case pass, wrong(Int), fail(ApiError) }
    enum IdResult: Equatable { case accepted, retry(String), fail(ApiError) }

    func reset() {
        session = nil
        challenge = nil
        otpSms = nil
        idFields = nil
        readyRetryChallenge = false
        requestedPurpose = nil
        dropFaceAttempt()
    }

    func dropFaceAttempt() {
        frontalJpeg = nil
        colorEvents.removeAll()
        pendingFaceVideo = nil
        pendingFaceImage = nil
        pendingSignals = nil
        pendingWav = nil
        pendingVoiceVideo = nil
        voicePayloadPrepared = false
        voiceRereads = 0
        audioOffsetMs = nil
        voicePrompt = nil
        voiceChallengeId = nil
        retryHint = nil
        attemptsLeft = nil
        mediaAcked = false
        signalsAcked = false
        voiceChecked = false
        readyRetryChallenge = false
    }

    func createSession(purpose: Purpose? = nil, scenario: String? = nil) async -> ApiError? {
        guard !busy else { return .busy }
        busy = true
        defer { busy = false }
        return await ensureSession(purpose: purpose, scenario: scenario)
    }

    private func ensureSession(purpose: Purpose?, scenario: String?) async -> ApiError? {
        if session != nil { return nil }
        var body: CreateSessionRequest?
        if let purpose {
            var bytes = [UInt8](repeating: 0, count: 18)
            guard SecRandomCopyBytes(kSecRandomDefault, bytes.count, &bytes) == errSecSuccess else { return .badResponse }
            let nonce = "ios_" + Data(bytes).base64EncodedString()
                .replacingOccurrences(of: "+", with: "-").replacingOccurrences(of: "/", with: "_")
                .replacingOccurrences(of: "=", with: "")
            body = CreateSessionRequest(purpose: purpose.rawValue, nonce: nonce)
        }
        switch await api.createSession(request: body, mockScenario: scenario) {
        case .failure(let error): return error
        case .success(let value):
            guard !value.sessionId.isEmpty, !value.token.isEmpty, !value.challenge.challengeId.isEmpty else { return .badResponse }
            session = value
            challenge = value.challenge
            requestedPurpose = purpose
            return nil
        }
    }

    // If no session exists, its first challenge is still fresh. Stage A sessions refresh here.
    // A finalize retry already supplied the next challenge, so it must not be refreshed again.
    func prepareFace(purpose: Purpose? = nil, scenario: String? = nil) async -> ApiError? {
        guard !busy else { return .busy }
        busy = true
        defer { busy = false }
        guard var current = session else { return await ensureSession(purpose: purpose, scenario: scenario) }
        if readyRetryChallenge { readyRetryChallenge = false; return nil }
        switch await api.refreshChallenge(sessionId: current.sessionId, token: current.token) {
        case .failure(let error): return error
        case .success(let value):
            guard !value.token.isEmpty, !value.challenge.challengeId.isEmpty else { return .badResponse }
            dropFaceAttempt()
            current.token = value.token
            current.expiresAt = value.expiresAt
            current.challenge = value.challenge
            session = current
            challenge = value.challenge
            return nil
        }
    }

    func sendOtp(phone: String, purpose: Purpose? = nil, scenario: String? = nil) async -> ApiError? {
        guard !busy else { return .busy }
        busy = true
        defer { busy = false }
        guard PhoneRules.isValid(phone) else { return .badResponse }
        if let error = await ensureSession(purpose: purpose, scenario: scenario) { return error }
        guard let current = session else { return .expired }
        switch await api.sendOtp(sessionId: current.sessionId, token: current.token, phone: phone) {
        case .failure(let error): return error
        case .success(let value):
            otpSms = value.simulatedSms
            attemptsLeft = value.attemptsLeft
            return nil
        }
    }

    func verifyOtp(code: String) async -> OtpResult {
        guard !busy else { return .fail(.busy) }
        busy = true
        defer { busy = false }
        guard let current = session else { return .fail(.expired) }
        guard OtpRules.isComplete(code) else { return .fail(.badResponse) }
        switch await api.verifyOtp(sessionId: current.sessionId, token: current.token, code: code) {
        case .failure(.conflict(code: "otp_already_verified")): return .pass
        case .failure(let error): return .fail(error)
        case .success(let value):
            attemptsLeft = value.attemptsLeft
            switch value.status {
            case "pass": return .pass
            case "retry": return .wrong(value.attemptsLeft)
            default: return .fail(.badResponse)
            }
        }
    }

    func sendIdCard(front: Data, back: Data, qr: String?) async -> IdResult {
        guard !busy else { return .fail(.busy) }
        busy = true
        defer { busy = false }
        guard let current = session else { return .fail(.expired) }
        switch await api.sendIdCard(sessionId: current.sessionId, token: current.token, front: front, back: back, qr: qr) {
        case .failure(let error): return .fail(error)
        case .success(let value):
            switch value.status {
            case "ok":
                guard let fields = value.fields else { return .fail(.badResponse) }
                idFields = fields
                return .accepted
            case "retry": idFields = nil; return .retry(value.retryHint ?? "QR_UNREADABLE")
            default: return .fail(.badResponse)
            }
        }
    }

    func confirmIdCard(fields: IdCardFields) async -> ApiError? {
        guard !busy else { return .busy }
        busy = true
        defer { busy = false }
        guard let current = session else { return .expired }
        switch await api.confirmIdCard(sessionId: current.sessionId, token: current.token, fields: fields) {
        case .failure(let error): return error
        case .success(let value):
            guard value.received else { return .badResponse }
            idFields = fields
            return nil
        }
    }

    func submitFace(video: Data? = nil, frameTimes: [FrameTime] = [], clientQuality: [String: JSONValue] = [:],
                    camprobe: CamProbe? = nil, regionMeans: [[String: JSONValue]]? = nil,
                    onMediaAcked: () -> Void = {}) async -> Next {
        guard !busy else { return .fail(.busy) }
        busy = true
        defer { busy = false }
        guard let current = session else { return .fail(.expired) }
        guard let active = challenge, let jpeg = frontalJpeg else { return .fail(.badResponse) }
        if pendingSignals == nil {
            pendingSignals = Signals(colorEvents: colorEvents, frameTimes: frameTimes, clientQuality: clientQuality,
                                     camprobe: camprobe, regionMeans: regionMeans, challengeId: active.challengeId)
            pendingFaceVideo = video
            pendingFaceImage = jpeg
        }
        guard let signals = pendingSignals else { return .fail(.badResponse) }
        if !mediaAcked {
            let ack = await api.sendMedia(sessionId: current.sessionId, token: current.token, imageJpeg: pendingFaceImage ?? jpeg,
                                          video: pendingFaceVideo, challengeId: active.challengeId)
            if let error = acknowledgmentError(ack, step: "media") { return .fail(error) }
            mediaAcked = true
            pendingFaceVideo = nil
            onMediaAcked()
        }
        if !signalsAcked {
            let ack = await api.sendSignals(sessionId: current.sessionId, token: current.token, signals: signals)
            if let error = acknowledgmentError(ack, step: "signals") { return .fail(error) }
            signalsAcked = true
        }
        switch await api.finalize(sessionId: current.sessionId, token: current.token, challengeId: active.challengeId) {
        case .failure(let error): return .fail(error)
        case .success(let value):
            guard let route = FlowRules.routeForStatus(value.status, retryHint: value.retryHint) else { return .fail(.badResponse) }
            if value.status == "retry" {
                guard let next = value.challenge, !next.challengeId.isEmpty else { return .fail(.badResponse) }
                dropFaceAttempt()
                challenge = next
                session?.challenge = next
                readyRetryChallenge = true
            }
            if value.status == "voice_challenge" {
                guard let prompt = value.voicePrompt, !prompt.isEmpty,
                      (current.purpose == nil && requestedPurpose == nil) || !(value.voiceChallengeId ?? "").isEmpty else { return .fail(.badResponse) }
                voicePrompt = prompt
                voiceChallengeId = value.voiceChallengeId
            }
            retryHint = value.retryHint
            attemptsLeft = value.attemptsLeft
            return .to(route)
        }
    }

    func submitVoice(wav: Data, video: Data? = nil, audioOffsetMs: Int? = nil, onAccepted: () -> Void = {}) async -> Next {
        guard !busy else { return .fail(.busy) }
        busy = true
        defer { busy = false }
        guard let current = session else { return .fail(.expired) }
        if !voicePayloadPrepared {
            let recording = pendingWav ?? wav
            guard !recording.isEmpty else { return .to(.noVoice) }
            pendingWav = recording
            pendingVoiceVideo = video
            self.audioOffsetMs = audioOffsetMs
            voicePayloadPrepared = true
        }
        guard let recording = pendingWav, !recording.isEmpty else { return .to(.noVoice) }
        guard (current.purpose == nil && requestedPurpose == nil) || !(voiceChallengeId ?? "").isEmpty else { return .fail(.badResponse) }
        switch await api.sendVoice(sessionId: current.sessionId, token: current.token, wav: recording,
                                   video: pendingVoiceVideo, audioOffsetMs: self.audioOffsetMs, voiceChallengeId: voiceChallengeId) {
        case .failure(let error): return .fail(error)
        case .success(let value):
            guard let route = FlowRules.routeForStatus(value.status, inVoiceStep: true) else { return .fail(.badResponse) }
            if value.status == "voice_challenge" {
                guard let prompt = value.voicePrompt, !prompt.isEmpty,
                      (current.purpose == nil && requestedPurpose == nil) || !(value.voiceChallengeId ?? "").isEmpty else { return .fail(.badResponse) }
                // attempts_left counts further re-reads AFTER this newly issued prompt;
                // zero still permits this last read. The contract caps re-reads at one.
                guard voiceRereads < 1, (value.attemptsLeft ?? 0) >= 0 else { return .fail(.badResponse) }
                if let nextId = value.voiceChallengeId, nextId == voiceChallengeId { return .fail(.badResponse) }
                voiceRereads += 1
                voicePrompt = prompt
                voiceChallengeId = value.voiceChallengeId
            }
            pendingWav = nil
            pendingVoiceVideo = nil
            voicePayloadPrepared = false
            self.audioOffsetMs = nil
            voiceChecked = true
            attemptsLeft = value.attemptsLeft
            onAccepted()
            return .to(route)
        }
    }

    private func acknowledgmentError(_ result: Result<StepAck, ApiError>, step: String) -> ApiError? {
        switch result {
        case .success(let ack): ack.received && ack.step == step ? nil : .badResponse
        case .failure(.conflict(code: "step_already_received")): nil
        case .failure(let error): error
        }
    }
}
