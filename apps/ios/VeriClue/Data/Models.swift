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

struct CreateSessionRequest: Codable, Equatable {
    let purpose: String
    let nonce: String
    var referenceImageId: String? = nil
}

struct CreateSessionResponse: Codable, Equatable {
    let sessionId: String
    var token: String
    var expiresAt: String
    var challenge: Challenge
    var purpose: String? = nil
    var nonce: String? = nil
}

struct ChallengeResponse: Codable, Equatable {
    let token: String
    let expiresAt: String
    let challenge: Challenge
}

struct OtpRequest: Codable, Equatable { let phone: String }
struct OtpVerifyRequest: Codable, Equatable { let code: String }
struct OtpSent: Codable, Equatable {
    let expiresAt: String
    let attemptsLeft: Int
    var simulatedSms: String? = nil
}
struct OtpVerifyResponse: Codable, Equatable {
    let status: String
    let attemptsLeft: Int
}

struct IdCardFields: Codable, Equatable {
    var fullName: String? = nil
    var idNumber: String? = nil
    var dateOfBirth: String? = nil
    var sex: String? = nil
    var address: String? = nil
    var issuedOn: String? = nil
}

struct IdCardResponse: Codable, Equatable {
    let status: String
    var fields: IdCardFields? = nil
    var retryHint: String? = nil
}
struct IdCardConfirmResponse: Codable, Equatable { let received: Bool }
struct StepAck: Codable, Equatable {
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
struct FinalizeResponse: Codable, Equatable {
    let status: String
    var retryHint: String? = nil
    var voicePrompt: String? = nil
    var attemptsLeft: Int? = nil
    var challenge: Challenge? = nil
    var voiceChallengeId: String? = nil
}
struct VoiceResponse: Codable, Equatable {
    let status: String
    var voicePrompt: String? = nil
    var attemptsLeft: Int? = nil
    var voiceChallengeId: String? = nil
}
struct ErrorResponse: Codable, Equatable {
    let errorCode: String
    let message: String
}

enum ApiError: Error, Equatable {
    case network, unauthorized, conflict(code: String?), expired, busy, badResponse, server
}
