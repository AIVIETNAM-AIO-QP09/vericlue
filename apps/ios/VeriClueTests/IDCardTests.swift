import CoreGraphics
import CoreImage
import Foundation
import ImageIO
import Testing
import UniformTypeIdentifiers
@testable import VeriClue

@MainActor
struct IDCardTests {
    @Test func QRMayBeOnEitherSideAndMalformedCandidatesAreSkipped() {
        let front = "000000000001||DEMO FRONT|01011995|Nam|DEMO"
        let back = "000000000002||DEMO BACK|01011995|Nam|DEMO"
        #expect(CCCDQR.select(front: front, back: nil) == front)
        #expect(CCCDQR.select(front: nil, back: back) == back)
        #expect(CCCDQR.select(front: front, back: back) == back)
        #expect(CCCDQR.select(front: front, back: "invalid") == front)
        #expect(CCCDQR.select(front: " ", back: "") == nil)
        #expect(CCCDQR.select(front: nil, back: nil) == nil)
        let photo = IDCardPhoto(jpeg: Data([1]), sharpness: 100, glareFraction: 0, qr: nil)
        #expect(photo.canContinue(isBack: false) && photo.canContinue(isBack: true))
        #expect(!IDCardPhoto(jpeg: Data(), sharpness: 100, glareFraction: 0, qr: front).canContinue(isBack: true))
    }

    @Test func emptyAndInvalidImagesFailClosed() {
        #expect(throws: IDCardError.self) { _ = try IDCardAnalyzer.analyze(Data()) }
        #expect(throws: IDCardError.self) { _ = try IDCardAnalyzer.analyze(Data([1, 2, 3])) }
        #expect(IDCardAnalyzer.laplacianVariance([], width: 0, height: 0) == 0)
        #expect(IDCardAnalyzer.glareFraction([], width: 0, height: 0) == 0)
    }

    @Test func flatBlurTextureAndGlareHaveExpectedMeasurements() {
        let flat = [UInt8](repeating: 100, count: 32 * 32)
        #expect(IDCardAnalyzer.laplacianVariance(flat, width: 32, height: 32) == 0)
        var texture: [UInt8] = []
        for index in 0..<1024 {
            let column: Int = index * 37
            let row: Int = (index / 32) * 71
            let value: Int = (column + row) % 256
            texture.append(UInt8(value))
        }
        #expect(IDCardAnalyzer.laplacianVariance(texture, width: 32, height: 32) > 60)
        #expect(IDCardAnalyzer.glareFraction(flat, width: 32, height: 32) == 0)
        #expect(IDCardAnalyzer.glareFraction([UInt8](repeating: 255, count: 32 * 32), width: 32, height: 32) == 1)
        #expect(!IDCardPhoto(jpeg: Data([1]), sharpness: 59, glareFraction: 0, qr: nil).canContinue(isBack: false))
        #expect(!IDCardPhoto(jpeg: Data([1]), sharpness: 100, glareFraction: 0.03, qr: nil).canContinue(isBack: false))
    }

    @Test func qrDecoderReadsSyntheticPayloadAndCropMatchesCardRatio() throws {
        let payload = "000000000001||NGUYEN VAN MAU|01011995|Nam|DIA CHI MAU|01012021"
        let filter = try #require(CIFilter(name: "CIQRCodeGenerator"))
        filter.setValue(Data(payload.utf8), forKey: "inputMessage")
        filter.setValue("M", forKey: "inputCorrectionLevel")
        let qr = try #require(filter.outputImage).transformed(by: CGAffineTransform(scaleX: 5, y: 5))
        let qrImage = try #require(CIContext().createCGImage(qr, from: qr.extent))
        let context = try #require(CGContext(data: nil, width: 634, height: 400, bitsPerComponent: 8, bytesPerRow: 0,
            space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue))
        context.setFillColor(CGColor(gray: 0.85, alpha: 1))
        context.fill(CGRect(x: 0, y: 0, width: 634, height: 400))
        context.setFillColor(CGColor(gray: 1, alpha: 1))
        context.fill(CGRect(x: 160, y: 40, width: 310, height: 310))
        context.interpolationQuality = .none
        context.draw(qrImage, in: CGRect(x: 180, y: 60, width: 270, height: 270))
        let image = try #require(context.makeImage())
        let bytes = NSMutableData()
        let destination = try #require(CGImageDestinationCreateWithData(bytes, UTType.jpeg.identifier as CFString, 1, nil))
        CGImageDestinationAddImage(destination, image, nil)
        #expect(CGImageDestinationFinalize(destination))
        let photo = try IDCardAnalyzer.analyze(bytes as Data)
        #expect(photo.qr == payload)
        #expect(photo.hasQR)
        let source = try #require(CGImageSourceCreateWithData(photo.jpeg as CFData, nil))
        let cropped = try #require(CGImageSourceCreateImageAtIndex(source, 0, nil))
        #expect(abs(Double(cropped.width) / Double(cropped.height) - 1.586) < 0.01)
        #expect(!CCCDQR.isPlausible("https://example.invalid"))
    }
}
