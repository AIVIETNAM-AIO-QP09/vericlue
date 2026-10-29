import CoreGraphics
import Foundation

enum FaceFramingState: String, Sendable {
    case noFace, multipleFaces, lowLight, tooFar, offCenter, good, trackerUnavailable

    nonisolated var guidance: String {
        switch self {
        case .noFace: "Đưa khuôn mặt vào khung"
        case .multipleFaces: "Chỉ để một người trong khung hình"
        case .lowLight: "Ra chỗ sáng hơn"
        case .tooFar: "Lại gần hơn"
        case .offCenter: "Đưa khuôn mặt vào giữa khung hình"
        case .good: "Tốt, giữ nguyên"
        case .trackerUnavailable: "Chưa nhận được khuôn mặt. Hãy thử lại."
        }
    }
}

struct FaceQualityResult: Sendable {
    let state: FaceFramingState
    let heldMs: Double
    let ready: Bool
}

struct QualityGate: Sendable {
    // Initial Android scaffold values, not a calibrated biometric decision.
    nonisolated static let minLuma = 70.0
    nonisolated static let minFaceWidth = 0.32
    nonisolated static let maxCenterOffset = 0.18
    nonisolated static let goodHoldMs = 1000.0
    nonisolated static let maxSampleGap = 0.25
    private var goodSince: Double?
    private var previousTimestamp: Double?

    nonisolated static func evaluate(_ signal: FaceSignal?, trackerFailed: Bool = false) -> FaceFramingState {
        if trackerFailed { return .trackerUnavailable }
        guard let signal, signal.faces > 0 else { return .noFace }
        guard signal.faces == 1 else { return .multipleFaces }
        guard let box = signal.box,
              [box.minX, box.minY, box.width, box.height].allSatisfy(\.isFinite),
              box.width > 0, box.height > 0, box.minX >= 0, box.minY >= 0, box.maxX <= 1, box.maxY <= 1,
              signal.brightness.isFinite, (0...255).contains(signal.brightness) else { return .trackerUnavailable }
        if signal.brightness < minLuma { return .lowLight }
        if box.width < minFaceWidth { return .tooFar }
        if abs(box.midX - 0.5) > maxCenterOffset || abs(box.midY - 0.45) > maxCenterOffset { return .offCenter }
        return .good
    }

    nonisolated mutating func reset() {
        goodSince = nil
        previousTimestamp = nil
    }

    nonisolated mutating func update(_ signal: FaceSignal?, trackerFailed: Bool = false) -> FaceQualityResult {
        let state = Self.evaluate(signal, trackerFailed: trackerFailed)
        guard state == .good, let time = signal?.timestamp, time.isFinite else {
            reset()
            return FaceQualityResult(state: state == .good ? .trackerUnavailable : state, heldMs: 0, ready: false)
        }
        if let previousTimestamp, time <= previousTimestamp || time - previousTimestamp > Self.maxSampleGap {
            goodSince = nil
        }
        previousTimestamp = time
        if goodSince == nil { goodSince = time }
        let elapsed = max(0, (time - (goodSince ?? time)) * 1000)
        return FaceQualityResult(state: .good, heldMs: min(Self.goodHoldMs, elapsed), ready: elapsed >= Self.goodHoldMs)
    }
}
