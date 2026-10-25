import CoreGraphics
import CoreVideo
import Foundation
import ImageIO
import Testing
@testable import VeriClue

@MainActor
struct ProbeRegionsTests {
    @Test func duplicateRatioIsExactAndBoundedToThirtyPairs() {
        var meter = DuplicateFrameMeter()
        #expect(meter.ratio == nil)
        let a = [UInt8](repeating: 80, count: 576), b = [UInt8](repeating: 81, count: 576)
        meter.add(a); meter.add(a); meter.add(b)
        #expect(meter.ratio == 0.5)
        for _ in 0..<100 { meter.add(b) }
        #expect(meter.pairs == 30)
        let ratio = meter.ratio
        meter.add(a)
        #expect(meter.ratio == ratio)
    }

    @Test func skinBoxesHaveAllFiveNamesAndBackgroundAvoidsExpandedFace() {
        let face = CGRect(x: 30, y: 30, width: 50, height: 70)
        let boxes = Regions.skinBoxes(face: face)
        #expect(Set(boxes.map { $0.0 }) == Set(["forehead", "left_cheek", "right_cheek", "nose", "chin"]))
        #expect(boxes.allSatisfy { face.contains($0.1) })
        #expect(Regions.backgroundBoxes(face: face, width: 100, height: 140).count == 2)
        let overlapping = CGRect(x: 0, y: 0, width: 100, height: 140)
        #expect(Regions.backgroundBoxes(face: overlapping, width: 100, height: 140).isEmpty)
    }

    @Test func regionJSONHasSixKeysAndMeasuredUnmirroredRGB() throws {
        let buffer = try pixels()
        let result = try #require(Regions.measure(buffer, box: CGRect(x: 0.25, y: 0.2, width: 0.5, height: 0.6), hostMs: 12345))
        #expect(result["t_ms"] == .number(12345))
        #expect(Regions.hasAllSixMeasured(result))
        let missingBackground = try #require(Regions.measure(buffer, box: CGRect(x: 0, y: 0, width: 1, height: 1), hostMs: 12346))
        #expect(!Regions.hasAllSixMeasured(missingBackground))
        guard case .object(let regions) = result["regions"] else { Issue.record("Missing regions"); return }
        #expect(regions.count == 6)
        for name in ["forehead", "left_cheek", "right_cheek", "nose", "chin", "background"] {
            guard case .object(let stat) = regions[name] else { Issue.record("Missing region"); continue }
            #expect(stat["rgb_all"] == .array([.number(120), .number(100), .number(80)]))
            #expect(stat["rgb_trim"] == stat["rgb_all"])
            #expect(stat["excluded_fraction"] == .number(0))
        }
        let signals = Signals(colorEvents: [], frameTimes: [], regionMeans: [result])
        #expect(try SessionJSON.decoder().decode(Signals.self, from: SessionJSON.encoder().encode(signals)).regionMeans == [result])
    }

    @Test func frontalCopyProducesRealJPEGFromSyntheticPixels() throws {
        let buffer = try pixels()
        let owned = try #require(FrontalPixels.copy(buffer))
        let jpeg = try #require(owned.jpeg())
        #expect(jpeg.prefix(2) == Data([0xff, 0xd8]))
        let source = try #require(CGImageSourceCreateWithData(jpeg as CFData, nil))
        let image = try #require(CGImageSourceCreateImageAtIndex(source, 0, nil))
        #expect(image.width == 96 && image.height == 128)
    }

    @Test func debugBuildDoesNotFlagItsExpectedAttachedDebugger() {
        let probe = DeviceProbe.collect()
        #expect(probe.deviceLabel?.isEmpty == false)
        #if DEBUG
        #expect(probe.apiTamperFlags?.contains("ios:debugger") == false)
        #expect(DeviceProbe.debuggerNote == "skipped_debug_build")
        #endif
        #if targetEnvironment(simulator)
        #expect(probe.apiTamperFlags?.contains("ios:simulator") == true)
        #expect(probe.apiTamperFlags?.contains("ios:jailbreak") == false)
        #endif
    }

    private func pixels() throws -> CVPixelBuffer {
        var buffer: CVPixelBuffer?
        #expect(CVPixelBufferCreate(kCFAllocatorDefault, 96, 128, kCVPixelFormatType_32BGRA, nil, &buffer) == kCVReturnSuccess)
        let result = try #require(buffer)
        CVPixelBufferLockBaseAddress(result, [])
        defer { CVPixelBufferUnlockBaseAddress(result, []) }
        let address = try #require(CVPixelBufferGetBaseAddress(result)).assumingMemoryBound(to: UInt8.self)
        let row = CVPixelBufferGetBytesPerRow(result)
        for y in 0..<128 {
            for x in 0..<96 {
                let i = y * row + x * 4
                address[i] = 80; address[i + 1] = 100; address[i + 2] = 120; address[i + 3] = 255
            }
        }
        return result
    }
}
