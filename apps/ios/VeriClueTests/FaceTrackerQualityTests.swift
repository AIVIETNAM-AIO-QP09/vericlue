import CoreGraphics
import CoreVideo
import Foundation
import Testing
import Vision
@testable import VeriClue

@MainActor
struct FaceTrackerQualityTests {
    private func face(_ time: Double = 0, width: Double = 0.45, x: Double = 0.5,
                      y: Double = 0.45, brightness: Double = 120, faces: Int = 1) -> FaceSignal {
        FaceSignal(faces: faces, box: CGRect(x: x - width / 2, y: y - 0.2, width: width, height: 0.4),
            yaw: nil, roll: nil, pitch: nil, brightness: brightness, timestamp: time)
    }

    @Test func gateShowsOnePrioritizedHintAndNeverAcceptsInvalidTracking() {
        #expect(QualityGate.evaluate(nil) == .noFace)
        #expect(QualityGate.evaluate(face(faces: 0)) == .noFace)
        #expect(QualityGate.evaluate(face(faces: 2)) == .multipleFaces)
        #expect(QualityGate.evaluate(face(width: 0.1, brightness: 30)) == .lowLight)
        #expect(QualityGate.evaluate(face(width: 0.2)) == .tooFar)
        #expect(QualityGate.evaluate(face(width: 0.2, x: 0.8)) == .tooFar)
        #expect(QualityGate.evaluate(face(width: 0.35, x: 0.8)) == .offCenter)
        #expect(QualityGate.evaluate(face(brightness: .nan)) == .trackerUnavailable)
        #expect(QualityGate.evaluate(face(), trackerFailed: true) == .trackerUnavailable)
        #expect(QualityGate.evaluate(face()) == .good)
    }

    @Test func goodMustBeContinuousAndCannotBridgeMissingSamplesOrBackground() {
        var gate = QualityGate()
        for time in [0.0, 0.2, 0.4, 0.6, 0.8] {
            let result = gate.update(face(time))
            #expect(!result.ready)
        }
        let ready = gate.update(face(1.0))
        #expect(ready.ready && ready.heldMs == 1000)
        let bad = gate.update(face(1.1, brightness: 30))
        #expect(!bad.ready && bad.heldMs == 0)
        let restarted = gate.update(face(1.2))
        #expect(!restarted.ready && restarted.heldMs == 0)
        let gap = gate.update(face(20))
        #expect(!gap.ready && gap.heldMs == 0)
        let duplicate = gate.update(face(20))
        #expect(!duplicate.ready && duplicate.heldMs == 0)
        gate.reset()
        let resumed = gate.update(face(100))
        #expect(!resumed.ready && resumed.heldMs == 0)
    }

    @Test func visionCoordinatesAnglesAndMissingPoseRemainExplicit() throws {
        let observation = VNFaceObservation(requestRevision: VNDetectFaceRectanglesRequestRevision3,
            boundingBox: CGRect(x: 0.1, y: 0.2, width: 0.4, height: 0.3),
            roll: NSNumber(value: Double.pi / 4), yaw: NSNumber(value: -Double.pi / 6), pitch: nil)
        let signal = FaceTracker.signal(from: [observation], brightness: 120, timestamp: 10)
        let box = try #require(signal.box)
        #expect(abs(box.minY - 0.5) < 0.0001)
        #expect(abs(try #require(signal.yaw) + 30) < 0.0001)
        #expect(abs(try #require(signal.roll) - 45) < 0.0001)
        #expect(signal.pitch == nil && signal.faces == 1)
        let empty = FaceTracker.signal(from: [], brightness: 120, timestamp: 11)
        #expect(empty.faces == 0 && empty.box == nil && empty.yaw == nil)
    }

    @Test func overlayMirrorsOnlyPreviewAndAccountsForAspectFillCrop() throws {
        let box = CGRect(x: 0.1, y: 0.2, width: 0.2, height: 0.4)
        let image = CGSize(width: 720, height: 1280)
        let view = CGSize(width: 96, height: 128)
        let normal = try #require(FacePreviewGeometry.rect(box: box, image: image, view: view, mirrored: false))
        let mirrored = try #require(FacePreviewGeometry.rect(box: box, image: image, view: view, mirrored: true))
        #expect(abs(normal.maxX + mirrored.minX - view.width) < 0.001)
        #expect(abs(normal.minY - 12.8) < 0.001)
        #expect(normal.minY == mirrored.minY && normal.size == mirrored.size)
        #expect(box.minX == 0.1)
        #expect(FacePreviewGeometry.rect(box: box, image: .zero, view: view, mirrored: true) == nil)
    }

    @Test func brightnessReadsBGRAPixelsNotAlphaOrRowPadding() throws {
        var buffer: CVPixelBuffer?
        let created = CVPixelBufferCreate(kCFAllocatorDefault, 17, 17, kCVPixelFormatType_32BGRA, nil, &buffer)
        #expect(created == kCVReturnSuccess)
        let pixels = try #require(buffer)
        #expect(CVPixelBufferLockBaseAddress(pixels, []) == kCVReturnSuccess)
        let address = try #require(CVPixelBufferGetBaseAddress(pixels)).assumingMemoryBound(to: UInt8.self)
        let stride = CVPixelBufferGetBytesPerRow(pixels)
        // Distinct white padding catches treating rowBytes as width * 4 when sampled at y=16.
        address.initialize(repeating: 255, count: stride * 17)
        for y in 0..<17 {
            for x in 0..<17 {
                let index = y * stride + 4 * x
                address[index] = 0
                address[index + 1] = 0
                address[index + 2] = 255
                address[index + 3] = 0
            }
        }
        CVPixelBufferUnlockBaseAddress(pixels, [])
        #expect(abs(FaceTracker.brightness(pixels) - 76.245) < 0.001)
    }
}
