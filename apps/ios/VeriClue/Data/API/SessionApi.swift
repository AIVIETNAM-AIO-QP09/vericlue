import Foundation

final class SessionApi {
    private let baseURL: URL
    private let session: URLSession

    // URLSession exposes an inactivity timeout and a total resource timeout, not separate
    // connect/read/write deadlines. This bounds idle waits at 15s and the complete transfer at 60s.
    static func configuration() -> URLSessionConfiguration {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 15
        config.timeoutIntervalForResource = 60
        config.waitsForConnectivity = false
        config.httpShouldSetCookies = false
        config.urlCache = nil
        return config
    }

    init(baseURL: URL, session: URLSession? = nil) {
        self.baseURL = baseURL
        self.session = session ?? URLSession(configuration: Self.configuration())
    }

    func createSession(request: CreateSessionRequest? = nil, mockScenario: String? = nil) async -> Result<CreateSessionResponse, ApiError> {
        do {
            var value = post(["v1", "sessions"], token: nil)
            value.httpBody = try request.map { try SessionJSON.encoder().encode($0) } ?? Data("{}".utf8)
            #if DEBUG
            if let mockScenario { value.setValue(mockScenario, forHTTPHeaderField: "X-Mock-Scenario") }
            #endif
            return await call(value)
        } catch { return .failure(.badResponse) }
    }

    func sendOtp(sessionId: String, token: String, phone: String) async -> Result<OtpSent, ApiError> {
        await json(sessionId, "otp", token, OtpRequest(phone: phone))
    }

    func verifyOtp(sessionId: String, token: String, code: String) async -> Result<OtpVerifyResponse, ApiError> {
        await json(sessionId, "otp/verify", token, OtpVerifyRequest(code: code))
    }

    func sendIdCard(sessionId: String, token: String, front: Data, back: Data, qr: String?) async -> Result<IdCardResponse, ApiError> {
        var body = MultipartBody()
        body.file("front", filename: "front.jpg", contentType: "image/jpeg", data: front)
        body.file("back", filename: "back.jpg", contentType: "image/jpeg", data: back)
        if let qr, !qr.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { body.field("qr", qr) }
        return await multipart(sessionId, "id-card", token, body)
    }

    func confirmIdCard(sessionId: String, token: String, fields: IdCardFields) async -> Result<IdCardConfirmResponse, ApiError> {
        await json(sessionId, "id-card/confirm", token, fields)
    }

    func refreshChallenge(sessionId: String, token: String) async -> Result<ChallengeResponse, ApiError> {
        await call(post(["v1", "sessions", sessionId, "challenge"], token: token))
    }

    func accountReceipt(sessionId: String, token: String) async -> Result<AccountReceipt, ApiError> {
        var request = post(["v1", "sessions", sessionId, "account"], token: token)
        request.httpMethod = "GET"
        request.setValue(nil, forHTTPHeaderField: "Content-Type")
        request.setValue("no-store", forHTTPHeaderField: "Cache-Control")
        return await call(request)
    }

    func sendMedia(sessionId: String, token: String, imageJpeg: Data, video: Data?, challengeId: String?) async -> Result<StepAck, ApiError> {
        var body = MultipartBody()
        body.file("image", filename: "face.jpg", contentType: "image/jpeg", data: imageJpeg)
        if let video { body.file("video", filename: "face.mp4", contentType: "video/mp4", data: video) }
        if let challengeId { body.field("challenge_id", challengeId) }
        return await multipart(sessionId, "media", token, body)
    }

    func sendSignals(sessionId: String, token: String, signals: Signals) async -> Result<StepAck, ApiError> {
        await json(sessionId, "signals", token, signals)
    }

    func finalize(sessionId: String, token: String, challengeId: String?) async -> Result<FinalizeResponse, ApiError> {
        if let challengeId { return await json(sessionId, "finalize", token, FinalizeRequest(challengeId: challengeId)) }
        return await call(post(["v1", "sessions", sessionId, "finalize"], token: token))
    }

    func sendVoice(sessionId: String, token: String, wav: Data, video: Data?, audioOffsetMs: Int?, voiceChallengeId: String?) async -> Result<VoiceResponse, ApiError> {
        guard audioOffsetMs.map({ (-5000...5000).contains($0) }) ?? true else { return .failure(.badResponse) }
        guard video != nil || audioOffsetMs == nil else { return .failure(.badResponse) }
        var body = MultipartBody()
        body.file("audio", filename: "voice.wav", contentType: "audio/wav", data: wav)
        if let video {
            body.file("video", filename: "voice.mp4", contentType: "video/mp4", data: video)
            if let audioOffsetMs { body.field("audio_offset_ms", String(audioOffsetMs)) }
        }
        if let voiceChallengeId { body.field("voice_challenge_id", voiceChallengeId) }
        return await multipart(sessionId, "voice", token, body)
    }

    static func errorFor(_ httpCode: Int, code: String?) -> ApiError {
        switch httpCode {
        case 401: .unauthorized
        case 409: .conflict(code: code)
        case 410: .expired
        case 429, 503: .busy
        case 400...499: .badResponse
        default: .server
        }
    }

    private func post(_ path: [String], token: String?) -> URLRequest {
        let url = path.reduce(baseURL) { $0.appendingPathComponent($1) }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token { request.setValue("Bearer " + token, forHTTPHeaderField: "Authorization") }
        return request
    }

    private func json<Body: Encodable, Response: Decodable>(_ id: String, _ endpoint: String, _ token: String, _ body: Body) async -> Result<Response, ApiError> {
        do {
            var request = post(["v1", "sessions", id] + endpoint.split(separator: "/").map(String.init), token: token)
            request.httpBody = try SessionJSON.encoder().encode(body)
            return await call(request)
        } catch { return .failure(.badResponse) }
    }

    private func multipart<Response: Decodable>(_ id: String, _ endpoint: String, _ token: String, _ body: MultipartBody) async -> Result<Response, ApiError> {
        var request = post(["v1", "sessions", id, endpoint], token: token)
        request.setValue(body.contentType, forHTTPHeaderField: "Content-Type")
        request.httpBody = body.data
        return await call(request)
    }

    private func call<Response: Decodable>(_ request: URLRequest) async -> Result<Response, ApiError> {
        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse else { return .failure(.badResponse) }
            guard (200...299).contains(http.statusCode) else {
                let code = (try? SessionJSON.decoder().decode(ErrorResponse.self, from: data))?.errorCode
                return .failure(Self.errorFor(http.statusCode, code: code))
            }
            return .success(try SessionJSON.decoder().decode(Response.self, from: data))
        } catch is DecodingError { return .failure(.badResponse) }
        catch { return .failure(.network) }
    }
}
