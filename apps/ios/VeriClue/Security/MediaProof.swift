import CryptoKit
import Foundation
import Security

enum ProofError: Error { case invalidContext, unavailableKey, keychain(OSStatus), signing }

nonisolated protocol MediaSigner: Sendable {
    nonisolated func publicKeySPKI() async throws -> String
    nonisolated func sign(_ message: Data) async throws -> String
}

enum MediaProof {
    nonisolated static let maxBytes = 64 * 1024 * 1024
    nonisolated private static let suffixes: Set<String> = [".jpg", ".jpeg", ".png", ".webp", ".mp4", ".webm", ".mov", ".wav", ".mp3", ".m4a", ".ogg"]

    struct FileDigest: Codable, Equatable, Sendable {
        let sha256: String
        let size: Int
        let suffix: String
    }

    private struct Manifest: Encodable, Sendable {
        let attempt_id: String
        let audio_offset_ms: Int?
        let challenge_id: String
        let client_nonce: String
        let files: [String: FileDigest]
        let nonce: String
        let `protocol` = "vericlue-media-v1"
        let purpose: String
        let session_id: String
        let stage: String

        // JSON null is part of the signed protocol, not an omitted optional field.
        enum CodingKeys: String, CodingKey {
            case attempt_id, audio_offset_ms, challenge_id, client_nonce, files, nonce, `protocol`, purpose, session_id, stage
        }
        nonisolated func encode(to encoder: Encoder) throws {
            var c = encoder.container(keyedBy: CodingKeys.self)
            try c.encode(attempt_id, forKey: .attempt_id)
            try c.encode(audio_offset_ms, forKey: .audio_offset_ms)
            try c.encode(challenge_id, forKey: .challenge_id)
            try c.encode(client_nonce, forKey: .client_nonce)
            try c.encode(files, forKey: .files)
            try c.encode(nonce, forKey: .nonce)
            try c.encode(`protocol`, forKey: .protocol)
            try c.encode(purpose, forKey: .purpose)
            try c.encode(session_id, forKey: .session_id)
            try c.encode(stage, forKey: .stage)
        }
    }

    nonisolated static func sha256(_ data: Data) -> String {
        // Two lowercase ASCII hex digits per byte, independent of formatting/locale.
        let digits = Array("0123456789abcdef".utf8)
        return String(decoding: SHA256.hash(data: data).flatMap {
            [digits[Int($0 >> 4)], digits[Int($0 & 15)]]
        }, as: UTF8.self)
    }

    nonisolated static func digest(name: String, bytes: Data) throws -> FileDigest {
        guard !bytes.isEmpty, bytes.count <= maxBytes else { throw ProofError.invalidContext }
        let ext = "." + (name as NSString).pathExtension.lowercased()
        return FileDigest(sha256: sha256(bytes), size: bytes.count, suffix: suffixes.contains(ext) ? ext : ".bin")
    }

    nonisolated static func manifest(session: CreateSessionResponse, challenge: Challenge, stage: String,
                         attemptID: String, files: [String: FileDigest], audioOffsetMs: Int? = nil) throws -> Data {
        guard let seed = challenge.mediaNonce, matches(seed, "[0-9a-f]{64}"),
              let clientNonce = session.nonce, let purpose = session.purpose,
              ["onboarding", "recovery", "reauth"].contains(purpose),
              [session.sessionId, challenge.challengeId, attemptID, clientNonce].allSatisfy({ matches($0, "[A-Za-z0-9_-]+") }),
              ["face", "voice"].contains(stage) else { throw ProofError.invalidContext }
        let roles: Set<String> = stage == "face" ? ["image", "video"] : ["audio", "video"]
        if let audioOffsetMs {
            guard stage == "voice", files["video"] != nil, (-5000...5000).contains(audioOffsetMs) else { throw ProofError.invalidContext }
        }
        guard Set(files.keys).isSubset(of: roles), files[stage == "face" ? "image" : "audio"] != nil,
              files.values.allSatisfy({ matches($0.sha256, "[0-9a-f]{64}") && (1...maxBytes).contains($0.size) &&
                  (suffixes.contains($0.suffix) || $0.suffix == ".bin") }) else { throw ProofError.invalidContext }
        let derived = sha256(Data("\(seed):\(stage):\(attemptID)".utf8))
        let value = Manifest(attempt_id: attemptID, audio_offset_ms: audioOffsetMs,
            challenge_id: challenge.challengeId, client_nonce: clientNonce, files: files,
            nonce: derived, purpose: purpose, session_id: session.sessionId, stage: stage)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
        return try encoder.encode(value)
    }

    nonisolated static func matches(_ value: String, _ pattern: String) -> Bool {
        value.range(of: "\\A(?:" + pattern + ")\\z", options: .regularExpression) != nil
    }
}
