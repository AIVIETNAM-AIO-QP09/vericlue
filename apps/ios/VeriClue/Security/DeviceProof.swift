import Foundation

enum DeviceProof {
    private struct Message: Decodable {
        let version: String
        let session_id: String
        let account_id: String
        let device_id: String
        let purpose: String
        let nonce: String
        let server_nonce: String
        let expires_at_ms: Int64
    }

    static func payload(session: CreateSessionResponse, account: AccountReceipt,
                        nonce: String, now: Date = Date()) throws -> Data {
        guard account.isUsable(at: now), let challenge = session.deviceChallenge,
              challenge.message.utf8.count <= 2048,
              let bytes = Data(base64Encoded: challenge.message),
              bytes.base64EncodedString() == challenge.message,
              bytes.allSatisfy({ (32...126).contains($0) }),
              let object = try JSONSerialization.jsonObject(with: bytes) as? [String: Any],
              Set(object.keys) == ["version", "session_id", "account_id", "device_id", "purpose", "nonce", "server_nonce", "expires_at_ms"]
        else { throw ProofError.invalidContext }
        let value = try JSONDecoder().decode(Message.self, from: bytes)
        let expiry = Date(timeIntervalSince1970: Double(value.expires_at_ms) / 1000)
        guard value.version == "vericlue-device-auth-v1", value.purpose == "reauth",
              session.purpose == "reauth", value.session_id == session.sessionId,
              value.account_id == account.accountId, value.device_id == account.deviceId,
              value.nonce == nonce, session.nonce == nonce,
              MediaProof.matches(value.server_nonce, "[0-9a-f]{64}"),
              let challengeExpiry = date(challenge.expiresAt), let sessionExpiry = date(session.expiresAt),
              let accountExpiry = account.expirationDate,
              abs(expiry.timeIntervalSince(challengeExpiry)) < 0.0005,
              expiry > now, expiry <= sessionExpiry, expiry <= accountExpiry
        else { throw ProofError.invalidContext }
        return bytes // Sign exact server bytes, never re-encode this JSON.
    }

    private static func date(_ raw: String) -> Date? {
        let parser = ISO8601DateFormatter()
        parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let value = parser.date(from: raw) { return value }
        parser.formatOptions = [.withInternetDateTime]
        return parser.date(from: raw)
    }
}
