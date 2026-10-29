import CoreImage
import CoreMedia
import CoreVideo
import Foundation
import ImageIO

struct FaceEvidence: Sendable {
    let jpeg: Data
    let frameTimes: [FrameTime]
    let regionMeans: [[String: JSONValue]]
    let duplicateRatio: Double?
    let aeAwbLocked: Bool
    let frontalAtMs: Double
    let firstHostSeconds: Double
    let clockDeltaMs: Double
    let diagnostics: [String: JSONValue]
}

// One independent pixel copy for the one frontal JPEG, never a camera-pool
// buffer retained by a slow encoder. Pixel storage is immutable after copying.
final class FrontalPixels: @unchecked Sendable {
    nonisolated(unsafe) private let buffer: CVPixelBuffer
    nonisolated private init(_ buffer: CVPixelBuffer) { self.buffer = buffer }

    nonisolated static func copy(_ source: CVPixelBuffer) -> FrontalPixels? {
        let width = CVPixelBufferGetWidth(source), height = CVPixelBufferGetHeight(source)
        var destination: CVPixelBuffer?
        guard CVPixelBufferCreate(kCFAllocatorDefault, width, height, kCVPixelFormatType_32BGRA,
                                  [kCVPixelBufferIOSurfacePropertiesKey: [:]] as CFDictionary, &destination) == kCVReturnSuccess,
              let destination, CVPixelBufferLockBaseAddress(source, .readOnly) == kCVReturnSuccess else { return nil }
        defer { CVPixelBufferUnlockBaseAddress(source, .readOnly) }
        guard CVPixelBufferLockBaseAddress(destination, []) == kCVReturnSuccess else { return nil }
        defer { CVPixelBufferUnlockBaseAddress(destination, []) }
        guard let from = CVPixelBufferGetBaseAddress(source), let to = CVPixelBufferGetBaseAddress(destination) else { return nil }
        let sourceRow = CVPixelBufferGetBytesPerRow(source), targetRow = CVPixelBufferGetBytesPerRow(destination)
        guard sourceRow >= width * 4, targetRow >= width * 4 else { return nil }
        for y in 0..<height { memcpy(to + y * targetRow, from + y * sourceRow, width * 4) }
        return FrontalPixels(destination)
    }

    nonisolated func jpeg() -> Data? {
        let image = CIImage(cvPixelBuffer: buffer)
        let context = CIContext(options: [.cacheIntermediates: false])
        return context.jpegRepresentation(of: image, colorSpace: CGColorSpaceCreateDeviceRGB(),
            options: [kCGImageDestinationLossyCompressionQuality as CIImageRepresentationOption: 0.9])
    }
}
