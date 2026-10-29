import Foundation

// Immutable ownership of one completed attempt. Never log or persist this binding.
struct FaceAttemptBinding: Equatable {
    let sessionID: String
    private let token: String
    let challenge: Challenge
    private let sessionDeadline: Date
    private let challengeDeadline: Date

    init?(session: CreateSessionResponse, challenge: Challenge) {
        func date(_ value: String) -> Date? {
            let parser = ISO8601DateFormatter()
            parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let result = parser.date(from: value) { return result }
            parser.formatOptions = [.withInternetDateTime]
            return parser.date(from: value)
        }
        // Dynamic capture must have its own deadline; never substitute the longer session TTL.
        guard challenge.dynamic == nil || challenge.expiresAt != nil,
              let sessionDeadline = date(session.expiresAt),
              let challengeDeadline = date(challenge.expiresAt ?? session.expiresAt) else { return nil }
        sessionID = session.sessionId; token = session.token; self.challenge = challenge
        self.sessionDeadline = sessionDeadline; self.challengeDeadline = challengeDeadline
    }

    func invalidRoute(session: CreateSessionResponse?, challenge: Challenge?, now: Date = Date()) -> Route? {
        guard let session, session.sessionId == sessionID else { return .errorSession }
        if now >= sessionDeadline || FlowRules.sessionExpired(session.expiresAt, now: now) { return .errorSession }
        guard session.token == token, challenge == self.challenge, now < challengeDeadline else { return .faceExpired }
        return nil
    }
}

struct PendingFaceCapture {
    let id = UUID()
    let videoURL: URL
    let evidence: FaceEvidence
    let probe: CamProbe
    let quality: [String: JSONValue]
    let events: [ColorEvent]
    let binding: FaceAttemptBinding
}
