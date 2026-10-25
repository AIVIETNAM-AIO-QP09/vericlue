import Foundation

enum FaceTimelineError: Error { case invalidChallenge, missedDisplayFrame, missingEvidence }

struct ColorEventLog: Sendable {
    private(set) var events: [ColorEvent] = []
    nonisolated init() {}

    nonisolated mutating func record(index: Int, rgb: String, targetSeconds: Double) throws {
        if events.last?.index == index { return }
        guard index == events.count, targetSeconds.isFinite, targetSeconds >= 0,
              events.last.map({ targetSeconds * 1000 > $0.paintedAt }) ?? true else {
            throw FaceTimelineError.missedDisplayFrame
        }
        events.append(ColorEvent(index: index, rgb: rgb, paintedAt: targetSeconds * 1000))
    }
}

struct TimelineRGB: Equatable, Sendable {
    let r: Double
    let g: Double
    let b: Double

    nonisolated init?(hex: String) {
        guard hex.count == 7, hex.first == "#", let value = UInt32(hex.dropFirst(), radix: 16) else { return nil }
        r = Double((value >> 16) & 255) / 255
        g = Double((value >> 8) & 255) / 255
        b = Double(value & 255) / 255
    }

    nonisolated init(r: Double, g: Double, b: Double) { self.r = r; self.g = g; self.b = b }

    nonisolated func interpolated(to next: TimelineRGB, fraction: Double) -> TimelineRGB {
        let f = min(1, max(0, fraction))
        if f == 0 { return self }
        if f == 1 { return next }
        return TimelineRGB(r: r + (next.r - r) * f, g: g + (next.g - g) * f, b: b + (next.b - b) * f)
    }
}

// Pure schedule. All offsets are from the first successfully written video frame.
struct FaceTimeline: Sendable {
    enum Phase: Equatable, Sendable {
        case baseline, color(Int), gap, gaze(Double, Double), head(Int, String), done
    }

    let challengeId: String
    let baselineMs: Int
    let frontalAtMs: Int
    let colors: [ColorStep]
    let gaze: [GazePoint]
    let headTurns: [String]
    let headStartMs: Int
    let headDurationMs: Int
    let endMs: Int
    let passive: Bool
    nonisolated static let grey = TimelineRGB(r: 209.0 / 255, g: 209.0 / 255, b: 209.0 / 255)

    nonisolated init(challenge: Challenge, passive: Bool) throws {
        guard !challenge.challengeId.isEmpty else { throw FaceTimelineError.invalidChallenge }
        challengeId = challenge.challengeId
        self.passive = passive
        if passive {
            baselineMs = 3000; frontalAtMs = 500; colors = []; gaze = []; headTurns = []
            headStartMs = 3000; headDurationMs = 0; endMs = 3000
            return
        }
        let baseline = challenge.baselineMs ?? 1000 // Schema default.
        guard let d = challenge.dynamic, d.version == 1,
              (1...5000).contains(baseline),
              (0..<baseline).contains(d.frontalCaptureAtMs),
              challenge.colorSequence.count == 8,
              challenge.colorSequence.allSatisfy({
                  TimelineRGB(hex: $0.rgb) != nil && (400...650).contains($0.holdMs) && $0.transitionMs == 150
              }),
              d.gazePoints.count == 8, d.headTurns.count == 3,
              Set(d.headTurns) == Set(["left", "right", "center"]), d.headTurns.last == "center",
              d.headDurationMs == 6000, (0...54000).contains(d.headStartAtMs),
              d.voiceStartAtMs == d.headStartAtMs + d.headDurationMs else { throw FaceTimelineError.invalidChallenge }
        let colorEnd = baseline + challenge.colorSequence.reduce(0) { $0 + $1.holdMs + $1.transitionMs }
        guard d.gazePoints.allSatisfy({ $0.x.isFinite && $0.y.isFinite && (0...1).contains($0.x) && (0...1).contains($0.y) }),
              d.gazePoints[0].atMs >= colorEnd,
              zip(d.gazePoints, d.gazePoints.dropFirst()).allSatisfy({ $0.atMs < $1.atMs }),
              d.gazePoints[7].atMs <= d.headStartAtMs else { throw FaceTimelineError.invalidChallenge }
        baselineMs = baseline; frontalAtMs = d.frontalCaptureAtMs; colors = challenge.colorSequence
        gaze = d.gazePoints; headTurns = d.headTurns
        headStartMs = d.headStartAtMs; headDurationMs = d.headDurationMs
        endMs = d.headStartAtMs + d.headDurationMs
    }

    nonisolated var colorsEndMs: Int { baselineMs + colors.reduce(0) { $0 + $1.holdMs + $1.transitionMs } }

    nonisolated func colorStartMs(_ index: Int) -> Int {
        baselineMs + colors.prefix(index).reduce(0) { $0 + $1.holdMs + $1.transitionMs }
    }

    nonisolated func phase(atMs t: Double) -> Phase {
        if t >= Double(endMs) { return .done }
        if t < Double(baselineMs) { return .baseline }
        for i in colors.indices where t < Double(colorStartMs(i) + colors[i].transitionMs + colors[i].holdMs) { return .color(i) }
        if t >= Double(headStartMs), !headTurns.isEmpty {
            let segment = min(headTurns.count - 1, Int((t - Double(headStartMs)) * Double(headTurns.count) / Double(headDurationMs)))
            return .head(segment, headTurns[segment])
        }
        guard let first = gaze.first, t >= Double(first.atMs) else { return .gap }
        for i in 0..<(gaze.count - 1) where t < Double(gaze[i + 1].atMs) {
            let a = gaze[i], b = gaze[i + 1]
            let f = min(1, max(0, (t - Double(a.atMs)) / Double(b.atMs - a.atMs)))
            return .gaze(a.x + (b.x - a.x) * f, a.y + (b.y - a.y) * f)
        }
        guard let last = gaze.last else { return .gap }
        return .gaze(last.x, last.y)
    }

    nonisolated func background(atMs t: Double) -> TimelineRGB {
        guard case .color(let i) = phase(atMs: t), let next = TimelineRGB(hex: colors[i].rgb) else {
            return t < Double(baselineMs) ? Self.grey : TimelineRGB(r: 1, g: 1, b: 1)
        }
        let previous = i == 0 ? Self.grey : (TimelineRGB(hex: colors[i - 1].rgb) ?? Self.grey)
        return previous.interpolated(to: next, fraction: (t - Double(colorStartMs(i))) / Double(colors[i].transitionMs))
    }
}
