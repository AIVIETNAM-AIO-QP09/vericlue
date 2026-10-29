import Combine
import Foundation
import Testing
@testable import VeriClue

@MainActor
struct FrontCameraSessionTests {
    @Test func stopIgnoresSynchronousPublishedObserverReentry() {
        let camera = FrontCameraSession()
        var notifications = 0
        let subscription = camera.$running.dropFirst().sink { _ in
            notifications += 1
            // Bound the regression itself: old stop() recursively publishes
            // four times rather than overflowing the test process's stack.
            if notifications < 4 { camera.stop() }
        }
        camera.stop()
        #expect(notifications == 1)
        #expect(!camera.running && !camera.recording && !camera.finishing)
        #expect(camera.snapshot == nil)
        withExtendedLifetime(subscription) {}
    }

    @Test func sampleDiagnosticsRejectInvalidValuesAndMeasureActualPTS() {
        var meter = FrontCameraFrameMeter()
        let invalidPTS = meter.record(pts: .nan, width: 720, height: 1280)
        let invalidSize = meter.record(pts: 1, width: 0, height: 1280)
        #expect(!invalidPTS)
        #expect(!invalidSize)
        #expect(meter.frames == 0)
        let first = meter.record(pts: 10, width: 720, height: 1280)
        #expect(first)
        for frame in 1...30 { _ = meter.record(pts: 10 + Double(frame) / 30, width: 720, height: 1280) }
        #expect(meter.frames == 31)
        #expect(abs(meter.fps - 30) < 0.01)
        #expect(meter.width == 720 && meter.height == 1280)
        meter.dropped()
        #expect(meter.droppedFrames == 1)
        meter.beginRun()
        #expect(meter.frames == 31 && meter.fps == 0)
        let resumed = meter.record(pts: 100, width: 720, height: 1280)
        #expect(resumed)
        #expect(meter.frames == 32)
    }

    @Test func controllerKeepsItsPipelineInstancesWithoutOpeningCamera() {
        let camera = FrontCameraSession()
        let session = camera.sessionID
        let output = camera.outputID
        let preview = camera.previewLayer
        camera.stop()
        #expect(camera.sessionID == session && camera.outputID == output)
        #expect(camera.previewLayer === preview)
        #expect(!camera.running && !camera.receivingFrames)
    }
}
