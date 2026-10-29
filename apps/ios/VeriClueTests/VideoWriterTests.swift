import CoreMedia
import Foundation
import Testing
@testable import VeriClue

@MainActor
struct VideoWriterTests {
    @Test func clockStartsAtFirstAcceptedFrameNotButtonOrCameraStart() throws {
        var clock = VideoFrameClock()
        // Seeing candidates does not advance t0. Only successful writer appends do.
        try clock.validate(CMTime(value: 30000, timescale: 30))
        #expect(clock.firstPTS == nil && clock.frameTimes.isEmpty)
        try clock.accepted(CMTime(value: 30002, timescale: 30))
        try clock.accepted(CMTime(value: 30005, timescale: 30))
        #expect(clock.firstPTS == CMTime(value: 30002, timescale: 30))
        #expect(clock.frameTimes.count == 2)
        #expect(clock.frameTimes.first?.mediaTime == 0)
        #expect(clock.frameTimes.last?.presentedFrames == 2)
        #expect(abs(try #require(clock.frameTimes.last?.mediaTime) - 0.1) < 0.000001)
        #expect(abs(try #require(clock.frameTimes.first?.captureTime) - (30002.0 / 30 * 1000)) < 0.000001)
    }

    @Test func invalidDuplicateBackwardEpochAndUnboundedFramesAreRejected() throws {
        var clock = VideoFrameClock()
        #expect(throws: VideoWriterError.self) { try clock.validate(.invalid) }
        try clock.accepted(CMTime(value: 10, timescale: 1))
        #expect(throws: VideoWriterError.self) { try clock.accepted(CMTime(value: 10, timescale: 1)) }
        #expect(throws: VideoWriterError.self) { try clock.accepted(CMTime(value: 9, timescale: 1)) }
        #expect(throws: VideoWriterError.self) { try clock.accepted(CMTime(value: 71, timescale: 1)) }
        var differentEpoch = CMTime(value: 11, timescale: 1)
        differentEpoch.epoch = 1
        #expect(throws: VideoWriterError.self) { try clock.accepted(differentEpoch) }
        #expect(clock.frameTimes.count == 1)
    }

    @Test func startupStallCannotBecomeAnExportableContinuousRecording() throws {
        var clock = VideoFrameClock()
        // Reproduce the uploaded clip's 0 -> 1 second gap, using synthetic PTS.
        try clock.accepted(CMTime(value: 1000, timescale: 30))
        #expect(throws: VideoWriterError.frameGap) {
            try clock.accepted(CMTime(value: 1030, timescale: 30))
        }
        #expect(clock.frameTimes.count == 1)
        #expect(clock.elapsed == 0)
        #expect(clock.lastPTS == clock.firstPTS)
    }

    @Test func normalCadenceAndSmallBackpressureDropsKeepOriginalTimestamps() throws {
        var clock = VideoFrameClock()
        for frame in [3000, 3001, 3002, 3005, 3006] {
            try clock.accepted(CMTime(value: Int64(frame), timescale: 30))
        }
        #expect(clock.frameTimes.count == 5)
        #expect(abs(clock.elapsed - 0.2) < 0.000001)
        #expect(abs(try #require(clock.frameTimes[3].mediaTime) - 5.0 / 30) < 0.000001)
        // A later stall is also rejected; the guard is not limited to startup.
        #expect(throws: VideoWriterError.frameGap) {
            try clock.accepted(CMTime(value: 3012, timescale: 30))
        }
        #expect(clock.frameTimes.count == 5)
    }

    @Test func finishWithoutSamplesFailsClosedAndDoesNotLeaveAnExportableFile() async throws {
        let queue = DispatchQueue(label: "vn.vericlue.writer-test")
        let writer = VideoWriter(queue: queue)
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("vericlue-writer-test-\(UUID()).mp4")
        do { _ = try await writer.finish(); Issue.record("Idle writer must not return a video") }
        catch { #expect(error as? VideoWriterError == .notRecording) }
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            queue.async {
                do { try writer.start(url: url); continuation.resume() }
                catch { continuation.resume(throwing: error) }
            }
        }
        do { _ = try await writer.finish(); Issue.record("Empty writer must not return a video") }
        catch { #expect(error as? VideoWriterError == .noFrames) }
        #expect(!FileManager.default.fileExists(atPath: url.path))
    }

    @Test func existingFileIsNeverOverwrittenOrDeletedByStart() async throws {
        let queue = DispatchQueue(label: "vn.vericlue.writer-existing-file-test")
        let writer = VideoWriter(queue: queue)
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("vericlue-existing-fixture-\(UUID()).mp4")
        let fixture = Data("synthetic existing file, not media".utf8)
        try fixture.write(to: url, options: .withoutOverwriting)
        defer { try? FileManager.default.removeItem(at: url) }
        do {
            try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
                queue.async {
                    do { try writer.start(url: url); continuation.resume() }
                    catch { continuation.resume(throwing: error) }
                }
            }
            Issue.record("Writer must not overwrite a supplied existing path")
        } catch { #expect(error as? VideoWriterError == .storage) }
        #expect(try Data(contentsOf: url) == fixture)
    }
}
