import CoreGraphics
import CoreVideo
import Foundation
import Vision

struct FaceSignal: Sendable {
    let faces: Int
    // Normalized TOP-left coordinates of upright, UNMIRRORED camera pixels.
    let box: CGRect?
    let yaw: Double?
    let roll: Double?
    let pitch: Double?
    let brightness: Double
    let timestamp: Double
}

struct FaceTrackingResult: Sendable {
    let signal: FaceSignal?
    let errorCode: Int?
    let errorDomain: String?
    let elapsedMs: Double
}

// Confined to FrontCameraWorker's serial sample queue, never shared across requests.
final class FaceTracker: @unchecked Sendable {
    nonisolated(unsafe) private let request: VNDetectFaceRectanglesRequest

    nonisolated init() {
        request = VNDetectFaceRectanglesRequest()
        request.revision = VNDetectFaceRectanglesRequestRevision3
    }

    nonisolated func analyze(_ buffer: CVPixelBuffer, timestamp: Double) -> FaceTrackingResult {
        let start = DispatchTime.now().uptimeNanoseconds
        do {
            // The video connection already rotates data to portrait and disables mirroring.
            try VNImageRequestHandler(cvPixelBuffer: buffer, orientation: .up).perform([request])
            let signal = Self.signal(from: request.results ?? [], brightness: Self.brightness(buffer), timestamp: timestamp)
            return FaceTrackingResult(signal: signal, errorCode: nil, errorDomain: nil,
                elapsedMs: Double(DispatchTime.now().uptimeNanoseconds - start) / 1e6)
        } catch {
            let failure = error as NSError
            return FaceTrackingResult(signal: nil, errorCode: failure.code, errorDomain: failure.domain,
                elapsedMs: Double(DispatchTime.now().uptimeNanoseconds - start) / 1e6)
        }
    }

    nonisolated static func signal(from observations: [VNFaceObservation], brightness: Double, timestamp: Double) -> FaceSignal {
        let face = observations.max { $0.boundingBox.width * $0.boundingBox.height < $1.boundingBox.width * $1.boundingBox.height }
        let visionBox = face?.boundingBox
        let box = visionBox.map { CGRect(x: $0.minX, y: 1 - $0.maxY, width: $0.width, height: $0.height) }
        return FaceSignal(faces: observations.count, box: box,
            yaw: degrees(face?.yaw), roll: degrees(face?.roll), pitch: degrees(face?.pitch),
            brightness: brightness, timestamp: timestamp)
    }

    nonisolated private static func degrees(_ radians: NSNumber?) -> Double? {
        guard let value = radians?.doubleValue, value.isFinite else { return nil }
        return value * 180 / .pi
    }

    // Whole-frame mean luma, like Android's gate; bounded sampling and no pixel copies.
    nonisolated static func brightness(_ buffer: CVPixelBuffer) -> Double {
        guard CVPixelBufferGetPixelFormatType(buffer) == kCVPixelFormatType_32BGRA,
              CVPixelBufferLockBaseAddress(buffer, .readOnly) == kCVReturnSuccess else { return .nan }
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        guard let address = CVPixelBufferGetBaseAddress(buffer) else { return .nan }
        let width = CVPixelBufferGetWidth(buffer)
        let height = CVPixelBufferGetHeight(buffer)
        let rowBytes = CVPixelBufferGetBytesPerRow(buffer)
        guard width > 0, height > 0, rowBytes / 4 >= width else { return .nan }
        let bytes = address.assumingMemoryBound(to: UInt8.self)
        var sum = 0.0
        var count = 0
        for y in stride(from: 0, to: height, by: 16) {
            for x in stride(from: 0, to: width, by: 16) {
                let index = y * rowBytes + x * 4
                sum += 0.114 * Double(bytes[index]) + 0.587 * Double(bytes[index + 1]) + 0.299 * Double(bytes[index + 2])
                count += 1
            }
        }
        return count > 0 ? sum / Double(count) : .nan
    }
}

enum FacePreviewGeometry {
    // Match portrait .resizeAspectFill and preview-only mirroring without changing data coordinates.
    nonisolated static func rect(box: CGRect, image: CGSize, view: CGSize, mirrored: Bool) -> CGRect? {
        let values = [box.minX, box.minY, box.width, box.height, image.width, image.height, view.width, view.height]
        guard values.allSatisfy(\.isFinite), box.width > 0, box.height > 0,
              image.width > 0, image.height > 0, view.width > 0, view.height > 0 else { return nil }
        let scale = max(view.width / image.width, view.height / image.height)
        let scaled = CGSize(width: image.width * scale, height: image.height * scale)
        let x = mirrored ? 1 - box.maxX : box.minX
        return CGRect(x: (view.width - scaled.width) / 2 + x * scaled.width,
                      y: (view.height - scaled.height) / 2 + box.minY * scaled.height,
                      width: box.width * scaled.width, height: box.height * scaled.height)
    }
}
