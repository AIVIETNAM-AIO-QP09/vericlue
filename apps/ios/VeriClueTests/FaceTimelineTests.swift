import Foundation
import Testing
@testable import VeriClue

@MainActor
struct FaceTimelineTests {
    @Test func displayLogUsesTargetTimestampOncePerSlotAndRejectsSkippedSlots() throws {
        var log = ColorEventLog()
        try log.record(index: 0, rgb: "#80e09e", targetSeconds: 1234.5)
        try log.record(index: 0, rgb: "#80e09e", targetSeconds: 1234.516)
        #expect(log.events.count == 1)
        #expect(log.events[0].paintedAt == 1234500)
        #expect(throws: FaceTimelineError.self) { try log.record(index: 2, rgb: "#73d9ff", targetSeconds: 1235) }
        #expect(throws: FaceTimelineError.self) { try log.record(index: 1, rgb: "#73d9ff", targetSeconds: 1234) }
        #expect(log.events.count == 1)
    }

    private func challenge() throws -> Challenge {
        try SessionJSON.decoder().decode(CreateSessionResponse.self, from: Fixtures.session(dynamic: true)).challenge
    }

    @Test func allFourPhasesUseTheExactServerScheduleAndHeadOrder() throws {
        let c = try challenge(), d = try #require(c.dynamic)
        let timeline = try FaceTimeline(challenge: c, passive: false)
        #expect(timeline.frontalAtMs == d.frontalCaptureAtMs)
        #expect(timeline.phase(atMs: 0) == .baseline)
        #expect(timeline.phase(atMs: Double(timeline.baselineMs)) == .color(0))
        for index in c.colorSequence.indices {
            #expect(timeline.phase(atMs: Double(timeline.colorStartMs(index))) == .color(index))
        }
        #expect(timeline.phase(atMs: Double(d.gazePoints[0].atMs)) == .gaze(d.gazePoints[0].x, d.gazePoints[0].y))
        for index in d.headTurns.indices {
            #expect(timeline.phase(atMs: Double(d.headStartAtMs + index * 2000)) == .head(index, d.headTurns[index]))
        }
        #expect(timeline.phase(atMs: Double(timeline.endMs) - 1) == .head(2, "center"))
        #expect(timeline.phase(atMs: Double(timeline.endMs)) == .done)
        #expect(timeline.endMs == d.voiceStartAtMs)
    }

    @Test func dotInterpolatesWithoutMirroringOrSwiftUIAnimation() throws {
        let c = try challenge(), d = try #require(c.dynamic)
        let timeline = try FaceTimeline(challenge: c, passive: false)
        let a = d.gazePoints[0], b = d.gazePoints[1]
        let p = timeline.phase(atMs: Double(a.atMs + b.atMs) / 2)
        guard case .gaze(let x, let y) = p else { Issue.record("Expected gaze"); return }
        #expect(abs(x - (a.x + b.x) / 2) < 0.000001)
        #expect(abs(y - (a.y + b.y) / 2) < 0.000001)
    }

    @Test func transitionUsesServerDurationThenHoldsExactRGB() throws {
        let c = try challenge(), timeline = try FaceTimeline(challenge: c, passive: false)
        let start = Double(timeline.colorStartMs(0))
        let target = try #require(TimelineRGB(hex: c.colorSequence[0].rgb))
        #expect(timeline.background(atMs: start) == FaceTimeline.grey)
        #expect(timeline.background(atMs: start + 150) == target)
        #expect(timeline.background(atMs: start + 75) == FaceTimeline.grey.interpolated(to: target, fraction: 0.5))
    }

    @Test func reauthIsPassiveEvenIfServerSuppliesALegacyColorShell() throws {
        let timeline = try FaceTimeline(challenge: challenge(), passive: true)
        #expect(timeline.colors.isEmpty && timeline.gaze.isEmpty && timeline.headTurns.isEmpty)
        #expect(timeline.frontalAtMs == 500 && timeline.endMs == 3000)
        #expect(timeline.phase(atMs: 2999) == .baseline)
        #expect(timeline.phase(atMs: 3000) == .done)
    }

    @Test func missingDynamicUnsafeColorsAndUnknownTurnsAreRejected() throws {
        var c = try challenge()
        c.dynamic = nil
        #expect(throws: FaceTimelineError.self) { _ = try FaceTimeline(challenge: c, passive: false) }
        let original = try challenge()
        let json = try #require(JSONSerialization.jsonObject(with: SessionJSON.encoder().encode(original)) as? [String: Any])
        for mutation in ["head_turns", "gaze_points", "color_sequence"] {
            var object = json
            var dynamic = try #require(object["dynamic"] as? [String: Any])
            if mutation == "head_turns" { dynamic["head_turns"] = ["left", "unknown", "center"] }
            if mutation == "gaze_points" {
                var points = try #require(dynamic["gaze_points"] as? [[String: Any]])
                points[1]["at_ms"] = points[0]["at_ms"]
                dynamic["gaze_points"] = points
            }
            object["dynamic"] = dynamic
            if mutation == "color_sequence" {
                var colors = try #require(object["color_sequence"] as? [[String: Any]])
                colors[0]["hold_ms"] = 1
                object["color_sequence"] = colors
            }
            let malformed = try SessionJSON.decoder().decode(Challenge.self, from: JSONSerialization.data(withJSONObject: object))
            #expect(throws: FaceTimelineError.self) { _ = try FaceTimeline(challenge: malformed, passive: false) }
        }
    }
}
