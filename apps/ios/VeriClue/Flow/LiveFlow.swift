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
    private var activeOperation: UUID?
    private var cancelRequest: (() -> Void)?
    private(set) var requiresFreshChallenge = false

    init(api: SessionApi) { self.api = api }

    enum OtpResult: Equatable { case pass, wrong(Int), fail(ApiError) }
    enum IdResult: Equatable { case accepted, retry(String), fail(ApiError) }

    func reset() {
        abandonOperation()
        session = nil
        challenge = nil
        otpSms = nil
        idFields = nil
        readyRetryChallenge = false
        requestedPurpose = nil
        dropFaceAttempt()
        requiresFreshChallenge = false
    }

    // Capture interruption is NOT a network retry. Revoke local ownership of any
    // in-flight reply and require /challenge before another upload is permitted.
    func abandonFaceAttempt() {
        abandonOperation()
        dropFaceAttempt()
        requiresFreshChallenge = true
    }

    func cancelPendingRequests() { abandonOperation() }

    private func abandonOperation() {
        let cancel = cancelRequest
        cancelRequest = nil
        activeOperation = nil
        cancel?()
    }

    private func beginOperation() -> UUID? {
        guard activeOperation == nil else { return nil }
        let id = UUID()
        activeOperation = id
        return id
    }

    private func endOperation(_ id: UUID) {
        guard activeOperation == id else { return }
        activeOperation = nil; cancelRequest = nil
    }

    private func request<Value: Sendable>(_ id: UUID,
        _ work: @escaping @MainActor () async -> Result<Value, ApiError>) async -> Result<Value, ApiError> {
        guard activeOperation == id, !Task.isCancelled else { return .failure(.network) }
        let task = Task { await work() }
        cancelRequest = { task.cancel() }
        let result = await withTaskCancellationHandler(operation: { await task.value }, onCancel: { task.cancel() })
        // A late success from an abandoned session/attempt must never set ack,
        // rotate a new run's token, invoke cleanup callbacks, or produce success.
        guard activeOperation == id, !Task.isCancelled else { return .failure(.network) }
        cancelRequest = nil
        return result
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
        guard let operation = beginOperation() else { return .busy }
        defer { endOperation(operation) }
        return await ensureSession(purpose: purpose, scenario: scenario, operation: operation)
    }

    private func ensureSession(purpose: Purpose?, scenario: String?, operation: UUID) async -> ApiError? {
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
        let bodyToSend = body
        switch await request(operation, { await self.api.createSession(request: bodyToSend, mockScenario: scenario) }) {
        case .failure(let error): return error
        case .success(let value):
            guard !value.sessionId.isEmpty, !value.token.isEmpty, !value.challenge.challengeId.isEmpty else { return .badResponse }
            session = value
            challenge = value.challenge
            requestedPurpose = purpose
            requiresFreshChallenge = false
            return nil
        }
    }

    // If no session exists, its first challenge is still fresh. Stage A sessions refresh here.
    // A finalize retry already supplied the next challenge, so it must not be refreshed again.
    func prepareFace(purpose: Purpose? = nil, scenario: String? = nil) async -> ApiError? {
        guard let operation = beginOperation() else { return .busy }
        defer { endOperation(operation) }
        guard var current = session else { return await ensureSession(purpose: purpose, scenario: scenario, operation: operation) }
        if readyRetryChallenge, !requiresFreshChallenge { readyRetryChallenge = false; return nil }
        let sessionToRefresh = current
        switch await request(operation, { await self.api.refreshChallenge(sessionId: sessionToRefresh.sessionId, token: sessionToRefresh.token) }) {
        case .failure(let error): return error
        case .success(let value):
            guard !value.token.isEmpty, !value.challenge.challengeId.isEmpty else { return .badResponse }
            dropFaceAttempt()
            current.token = value.token
            current.expiresAt = value.expiresAt
            current.challenge = value.challenge
            session = current
            challenge = value.challenge
            requiresFreshChallenge = false
            return nil
        }
    }

    func sendOtp(phone: String, purpose: Purpose? = nil, scenario: String? = nil) async -> ApiError? {
        guard let operation = beginOperation() else { return .busy }
        defer { endOperation(operation) }
        guard PhoneRules.isValid(phone) else { return .badResponse }
        if let error = await ensureSession(purpose: purpose, scenario: scenario, operation: operation) { return error }
        guard let current = session else { return .expired }
        switch await request(operation, { await self.api.sendOtp(sessionId: current.sessionId, token: current.token, phone: phone) }) {
        case .failure(let error): return error
        case .success(let value):
            otpSms = value.simulatedSms
            attemptsLeft = value.attemptsLeft
            return nil
        }
    }

    func verifyOtp(code: String) async -> OtpResult {
        guard let operation = beginOperation() else { return .fail(.busy) }
        defer { endOperation(operation) }
        guard let current = session else { return .fail(.expired) }
        guard OtpRules.isComplete(code) else { return .fail(.badResponse) }
        switch await request(operation, { await self.api.verifyOtp(sessionId: current.sessionId, token: current.token, code: code) }) {
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
        guard let operation = beginOperation() else { return .fail(.busy) }
        defer { endOperation(operation) }
        guard let current = session else { return .fail(.expired) }
        switch await request(operation, { await self.api.sendIdCard(sessionId: current.sessionId, token: current.token, front: front, back: back, qr: qr) }) {
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
        guard let operation = beginOperation() else { return .busy }
        defer { endOperation(operation) }
        guard let current = session else { return .expired }
        switch await request(operation, { await self.api.confirmIdCard(sessionId: current.sessionId, token: current.token, fields: fields) }) {
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
        guard let operation = beginOperation() else { return .fail(.busy) }
        defer { endOperation(operation) }
        guard !requiresFreshChallenge else { return .fail(.conflict(code: "challenge_expired")) }
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
            let image = pendingFaceImage ?? jpeg, video = pendingFaceVideo
            let ack = await request(operation) {
                await self.api.sendMedia(sessionId: current.sessionId, token: current.token, imageJpeg: image,
                                         video: video, challengeId: active.challengeId)
            }
            if let error = acknowledgmentError(ack, step: "media") { return .fail(error) }
            mediaAcked = true
            pendingFaceVideo = nil
            onMediaAcked()
        }
        if !signalsAcked {
            let ack = await request(operation) { await self.api.sendSignals(sessionId: current.sessionId, token: current.token, signals: signals) }
            if let error = acknowledgmentError(ack, step: "signals") { return .fail(error) }
            signalsAcked = true
        }
        switch await request(operation, { await self.api.finalize(sessionId: current.sessionId, token: current.token, challengeId: active.challengeId) }) {
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
        guard let operation = beginOperation() else { return .fail(.busy) }
        defer { endOperation(operation) }
        guard !requiresFreshChallenge else { return .fail(.conflict(code: "challenge_expired")) }
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
        let video = pendingVoiceVideo, offset = self.audioOffsetMs, voiceID = voiceChallengeId
        switch await request(operation, { await self.api.sendVoice(sessionId: current.sessionId, token: current.token, wav: recording,
                                   video: video, audioOffsetMs: offset, voiceChallengeId: voiceID) }) {
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
