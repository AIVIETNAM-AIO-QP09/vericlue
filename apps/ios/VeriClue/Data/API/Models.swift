import Foundation

// Property names deliberately use `Id`/`Ms`: the shared codec maps them to snake_case.
enum SessionJSON {
    static func decoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }

    static func encoder() -> JSONEncoder {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }
}

struct ColorStep: Codable, Equatable, Sendable {
    let rgb: String
    let holdMs: Int
    let transitionMs: Int
}

struct Challenge: Codable, Equatable, Sendable {
    let challengeId: String
    let colorSequence: [ColorStep]
    var baselineMs: Int? = nil
    var captureAtMs: [Int]? = nil
    var expiresAt: String? = nil
    var dynamic: DynamicChallenge? = nil
}

struct GazePoint: Codable, Equatable, Sendable {
    let x: Double
    let y: Double
    let atMs: Int
}

struct DynamicChallenge: Codable, Equatable, Sendable {
    let version: Int
    let sessionId: String
    let nonce: String
    let gazePoints: [GazePoint]
    let headTurns: [String]
    let headStartAtMs: Int
    let headDurationMs: Int
    let voiceStartAtMs: Int
    let voicePrompt: String
    let voiceChallengeId: String
    let frontalCaptureAtMs: Int
}

struct CreateSessionRequest: Codable, Equatable, Sendable {
    let purpose: String
    let nonce: String
    var referenceImageId: String? = nil
}

struct CreateSessionResponse: Codable, Equatable, Sendable {
    let sessionId: String
    var token: String
    var expiresAt: String
    var challenge: Challenge
    var purpose: String? = nil
    var nonce: String? = nil
}

struct ChallengeResponse: Codable, Equatable, Sendable {
    let token: String
    let expiresAt: String
    let challenge: Challenge
}

struct OtpRequest: Codable, Equatable { let phone: String }
struct OtpVerifyRequest: Codable, Equatable { let code: String }
struct OtpSent: Codable, Equatable, Sendable {
    let expiresAt: String
    let attemptsLeft: Int
    var simulatedSms: String? = nil
}
struct OtpVerifyResponse: Codable, Equatable, Sendable {
    let status: String
    let attemptsLeft: Int
}

struct IdCardFields: Codable, Equatable, Sendable {
    var fullName: String? = nil
    var idNumber: String? = nil
    var dateOfBirth: String? = nil
    var sex: String? = nil
    var address: String? = nil
    var issuedOn: String? = nil
}

struct IdCardResponse: Codable, Equatable, Sendable {
    let status: String
    var fields: IdCardFields? = nil
    var retryHint: String? = nil
}
struct IdCardConfirmResponse: Codable, Equatable, Sendable { let received: Bool }
struct StepAck: Codable, Equatable, Sendable {
    let step: String
    let received: Bool
}
struct ColorEvent: Codable, Equatable, Sendable {
    let index: Int
    let rgb: String
    let paintedAt: Double
}
struct FrameTime: Codable, Equatable, Sendable {
    var captureTime: Double? = nil
    var presentedFrames: Int? = nil
    var mediaTime: Double? = nil
}

// The schema leaves these diagnostic dictionaries open, including numeric/bool values.
enum JSONValue: Codable, Equatable, Sendable {
    case string(String), number(Double), bool(Bool), object([String: JSONValue]), array([JSONValue]), null

    init(from decoder: Decoder) throws {
        let value = try decoder.singleValueContainer()
        if value.decodeNil() { self = .null }
        else if let bool = try? value.decode(Bool.self) { self = .bool(bool) }
        else if let number = try? value.decode(Double.self) { self = .number(number) }
        else if let string = try? value.decode(String.self) { self = .string(string) }
        else if let array = try? value.decode([JSONValue].self) { self = .array(array) }
        else { self = .object(try value.decode([String: JSONValue].self)) }
    }

    func encode(to encoder: Encoder) throws {
        var value = encoder.singleValueContainer()
        switch self {
        case .string(let item): try value.encode(item)
        case .number(let item): try value.encode(item)
        case .bool(let item): try value.encode(item)
        case .object(let item): try value.encode(item)
        case .array(let item): try value.encode(item)
        case .null: try value.encodeNil()
        }
    }
}

struct CamProbe: Codable, Equatable, Sendable {
    var apiTamperFlags: [String]? = nil
    var constraintProbes: [[String: JSONValue]]? = nil
    var deviceLabel: String? = nil
    var trackSettings: [String: JSONValue]? = nil
    var trackCapabilities: [String: JSONValue]? = nil
    var duplicateFrameRatio: Double? = nil
}

struct Signals: Codable, Equatable, Sendable {
    let colorEvents: [ColorEvent]
    let frameTimes: [FrameTime]
    var clientQuality: [String: JSONValue]? = nil
    var camprobe: CamProbe? = nil
    var regionMeans: [[String: JSONValue]]? = nil
    var challengeId: String? = nil
}

struct FinalizeRequest: Codable, Equatable { let challengeId: String }
struct FinalizeResponse: Codable, Equatable, Sendable {
    let status: String
    var retryHint: String? = nil
    var voicePrompt: String? = nil
    var attemptsLeft: Int? = nil
    var challenge: Challenge? = nil
    var voiceChallengeId: String? = nil
}
struct VoiceResponse: Codable, Equatable, Sendable {
    let status: String
    var voicePrompt: String? = nil
    var attemptsLeft: Int? = nil
    var voiceChallengeId: String? = nil
    var account: AccountReceipt? = nil
}

extension VoiceResponse {
    init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        status = try values.decode(String.self, forKey: .status)
        voicePrompt = try values.decodeIfPresent(String.self, forKey: .voicePrompt)
        attemptsLeft = try values.decodeIfPresent(Int.self, forKey: .attemptsLeft)
        voiceChallengeId = try values.decodeIfPresent(String.self, forKey: .voiceChallengeId)
        // Receipt is ancillary metadata. A malformed receipt cannot undo a valid
        // verification result; GET /account may recover it after a pass.
        account = try? values.decodeIfPresent(AccountReceipt.self, forKey: .account)
    }
}

// Published contract at Android reference f034fa9, session.schema.json $defs.AccountReceipt.
// A reference to an enrollment, NOT a credential or a bank account number.
struct AccountReceipt: Codable, Equatable, Sendable {
    let accountId: String
    let deviceId: String
    let expiresAt: String

    private enum CodingKeys: String, CodingKey { case accountId, deviceId, expiresAt }

    nonisolated var expirationDate: Date? {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: expiresAt) { return date }
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: expiresAt)
    }

    nonisolated var isWellFormed: Bool {
        Self.validId(accountId, prefix: "acct_") && Self.validId(deviceId, prefix: "dev_") && expirationDate != nil
    }

    nonisolated func isUsable(at now: Date = Date()) -> Bool {
        isWellFormed && (expirationDate.map { $0 > now } ?? false)
    }

    nonisolated private static func validId(_ value: String, prefix: String) -> Bool {
        guard value.hasPrefix(prefix) else { return false }
        let suffix = value.dropFirst(prefix.count).utf8
        return suffix.count == 32 && suffix.allSatisfy { (48...57).contains($0) || (97...102).contains($0) }
    }
}

extension AccountReceipt {
    nonisolated func encode(to encoder: Encoder) throws {
        var values = encoder.container(keyedBy: CodingKeys.self)
        try values.encode(accountId, forKey: .accountId)
        try values.encode(deviceId, forKey: .deviceId)
        try values.encode(expiresAt, forKey: .expiresAt)
    }

    nonisolated init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        accountId = try values.decode(String.self, forKey: .accountId)
        deviceId = try values.decode(String.self, forKey: .deviceId)
        expiresAt = try values.decode(String.self, forKey: .expiresAt)
        guard isWellFormed else {
            throw DecodingError.dataCorrupted(.init(codingPath: decoder.codingPath,
                debugDescription: "Invalid account receipt"))
        }
    }
}
struct ErrorResponse: Codable, Equatable {
    let errorCode: String
    let message: String
}

enum ApiError: Error, Equatable, Sendable {
    case network, unauthorized, conflict(code: String?), expired, busy, badResponse, server
}
