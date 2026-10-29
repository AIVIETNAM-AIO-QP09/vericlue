import Foundation

// Android timings are reference settings, not measured iPhone performance.
struct IDAutoCapture {
    static let startDelay = 1.5
    static let sampleInterval = 0.5
    static let pause = 1.5
    private(set) var consecutive = 0
    private var startedAt: Double?
    private var lastSample: Double?
    private(set) var claimed = false

    mutating func begin(at time: Double) {
        startedAt = time; lastSample = nil; consecutive = 0; claimed = false
    }

    mutating func offer(good: Bool, at time: Double) -> Bool {
        guard !claimed, let startedAt, time >= startedAt + Self.startDelay else { return false }
        if let lastSample, time - lastSample < Self.sampleInterval { return false }
        // A long pause/slow inference cannot turn stale samples into a stable run.
        if let lastSample, time - lastSample > Self.sampleInterval * 3 { consecutive = 0 }
        lastSample = time
        consecutive = good ? consecutive + 1 : 0
        return consecutive >= 2
    }

    mutating func claim() -> Bool {
        guard startedAt != nil, !claimed else { return false }
        claimed = true
        return true
    }

    mutating func cancel() { startedAt = nil; lastSample = nil; consecutive = 0; claimed = false }
}

enum CardText {
    nonisolated private static let words = ["CAN CUOC", "CONG DAN", "CITIZEN", "IDENTITY", "IDVNM", "CONG HOA",
        "SOCIALIST REPUBLIC", "QUOC TICH", "NATIONALITY", "DAC DIEM NHAN DANG",
        "PERSONAL IDENTIFICATION", "NGAY CAP", "DATE OF ISSUE"]

    nonisolated static func looksLikeCard(_ text: String) -> Bool {
        let plain = text.uppercased().folding(options: .diacriticInsensitive, locale: Locale(identifier: "vi_VN"))
            .replacingOccurrences(of: "Đ", with: "D")
            .split(whereSeparator: \.isWhitespace).joined(separator: " ")
        return words.contains(where: plain.contains)
    }
}

struct IDCardObservation: Sendable {
    let sharpness: Double
    let glareFraction: Double
    let looksLikeCard: Bool
    let hasQR: Bool
    let sampledAt: Double

    var qualityGood: Bool { sharpness >= 60 && glareFraction <= 0.02 }
    func good(isBack _: Bool) -> Bool { qualityGood && looksLikeCard }
}
