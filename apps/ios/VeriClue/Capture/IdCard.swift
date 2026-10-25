import Accelerate
import CoreGraphics
import CoreImage
import Foundation
import ImageIO
import UniformTypeIdentifiers
import Vision

enum IDCardError: Error { case emptyImage, unreadableImage, processingFailed }

struct IDCardPhoto: Sendable {
    let jpeg: Data
    let sharpness: Double
    let glareFraction: Double
    let qr: String?

    // Starting thresholds copied from Android IdQuality, not calibrated iPhone measurements.
    var sharp: Bool { sharpness >= 60 }
    var noGlare: Bool { glareFraction <= 0.02 }
    var hasQR: Bool { CCCDQR.isPlausible(qr) }
    func canContinue(isBack: Bool) -> Bool { sharp && noGlare && (!isBack || hasQR) }
}

enum CCCDQR {
    // Local formatting gate only. Server remains the source of the displayed identity fields.
    nonisolated static func isPlausible(_ raw: String?) -> Bool {
        guard let raw else { return false }
        let fields = raw.components(separatedBy: "|")
        guard fields.count >= 6 else { return false }
        let id = fields[0].trimmingCharacters(in: .whitespacesAndNewlines)
        return id.count == 12 && id.allSatisfy { $0.isASCII && $0.isNumber }
    }
}

enum IDCardAnalyzer {
    nonisolated static func analyze(_ data: Data) throws -> IDCardPhoto {
        guard !data.isEmpty else { throw IDCardError.emptyImage }
        guard let source = CGImageSourceCreateWithData(data as CFData, nil),
              let upright = CGImageSourceCreateThumbnailAtIndex(source, 0, [
                kCGImageSourceCreateThumbnailFromImageAlways: true,
                kCGImageSourceCreateThumbnailWithTransform: true,
                kCGImageSourceThumbnailMaxPixelSize: 1600
              ] as CFDictionary) else { throw IDCardError.unreadableImage }
        // Same aspect-fill, centered card viewport as the rear preview. Normalize EXIF first.
        let targetRatio = 1.586
        let width = min(Double(upright.width), Double(upright.height) * targetRatio)
        let height = width / targetRatio
        let rect = CGRect(x: (Double(upright.width) - width) / 2,
                          y: (Double(upright.height) - height) / 2, width: width, height: height).integral
        guard let card = upright.cropping(to: rect), card.width >= 3, card.height >= 3 else {
            throw IDCardError.unreadableImage
        }
        var luma = [UInt8](repeating: 0, count: card.width * card.height)
        let drawn = luma.withUnsafeMutableBytes { bytes -> Bool in
            guard let context = CGContext(data: bytes.baseAddress, width: card.width, height: card.height,
                bitsPerComponent: 8, bytesPerRow: card.width, space: CGColorSpaceCreateDeviceGray(),
                bitmapInfo: CGImageAlphaInfo.none.rawValue) else { return false }
            context.draw(card, in: CGRect(x: 0, y: 0, width: card.width, height: card.height))
            return true
        }
        guard drawn else { throw IDCardError.processingFailed }
        let qr = try decodeQR(in: card)
        let jpeg = NSMutableData()
        guard let destination = CGImageDestinationCreateWithData(jpeg, UTType.jpeg.identifier as CFString, 1, nil) else {
            throw IDCardError.processingFailed
        }
        CGImageDestinationAddImage(destination, card, [kCGImageDestinationLossyCompressionQuality: 0.9] as CFDictionary)
        guard CGImageDestinationFinalize(destination), jpeg.length > 0 else { throw IDCardError.processingFailed }
        return IDCardPhoto(jpeg: jpeg as Data,
            sharpness: laplacianVariance(luma, width: card.width, height: card.height),
            glareFraction: glareFraction(luma, width: card.width, height: card.height), qr: qr)
    }

    nonisolated private static func decodeQR(in card: CGImage) throws -> String? {
        let request = VNDetectBarcodesRequest()
        request.symbologies = [.qr]
        do {
            try VNImageRequestHandler(cgImage: card).perform([request])
            return request.results?.compactMap(\.payloadStringValue).first { !$0.isEmpty }
        } catch {
            #if targetEnvironment(simulator)
            // Some Simulator runtimes cannot create Vision's inference context (Code 9).
            // Decode the actual pixels instead; never substitute a known fixture payload.
            let failure = error as NSError
            guard failure.domain == VNErrorDomain, failure.code == VNErrorCode.internalError.rawValue else {
                throw error
            }
            let context = CIContext(options: [.useSoftwareRenderer: true])
            guard let detector = CIDetector(ofType: CIDetectorTypeQRCode, context: context,
                options: [CIDetectorAccuracy: CIDetectorAccuracyHigh]) else { throw error }
            return detector.features(in: CIImage(cgImage: card))
                .compactMap { ($0 as? CIQRCodeFeature)?.messageString }.first { !$0.isEmpty }
            #else
            // Device inference failures remain failures, not an unreadable-QR success path.
            throw error
            #endif
        }
    }

    nonisolated static func laplacianVariance(_ luma: [UInt8], width: Int, height: Int) -> Double {
        guard width >= 3, height >= 3, luma.count / width >= height else { return 0 }
        var input = luma.prefix(width * height).map(Float.init)
        var output = [Float](repeating: 0, count: width * height)
        let kernel: [Float] = [0, 1, 0, 1, -4, 1, 0, 1, 0]
        let error = input.withUnsafeMutableBytes { source in
            output.withUnsafeMutableBytes { destination in
                var src = vImage_Buffer(data: source.baseAddress!, height: vImagePixelCount(height),
                    width: vImagePixelCount(width), rowBytes: width * MemoryLayout<Float>.size)
                var dst = vImage_Buffer(data: destination.baseAddress!, height: vImagePixelCount(height),
                    width: vImagePixelCount(width), rowBytes: width * MemoryLayout<Float>.size)
                return vImageConvolve_PlanarF(&src, &dst, nil, 0, 0, kernel, 3, 3, 0, vImage_Flags(kvImageEdgeExtend))
            }
        }
        guard error == kvImageNoError else { return 0 }
        var sum = 0.0
        var sumSquared = 0.0
        var count = 0
        for y in stride(from: 1, to: height - 1, by: 2) {
            for x in stride(from: 1, to: width - 1, by: 2) {
                let value = Double(output[y * width + x])
                sum += value
                sumSquared += value * value
                count += 1
            }
        }
        guard count > 0 else { return 0 }
        let mean = sum / Double(count)
        return max(0, sumSquared / Double(count) - mean * mean)
    }

    nonisolated static func glareFraction(_ luma: [UInt8], width: Int, height: Int) -> Double {
        guard width > 0, height > 0, luma.count / width >= height else { return 0 }
        var bright = 0
        var count = 0
        for y in stride(from: 0, to: height, by: 4) {
            for x in stride(from: 0, to: width, by: 4) {
                if luma[y * width + x] >= 250 { bright += 1 }
                count += 1
            }
        }
        return count == 0 ? 0 : Double(bright) / Double(count)
    }
}
