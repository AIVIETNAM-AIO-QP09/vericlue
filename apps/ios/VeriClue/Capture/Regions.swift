import CoreGraphics
import CoreVideo
import Foundation

struct RegionStat: Equatable, Sendable {
    let rgbAll: [Int]?
    let rgbTrim: [Int]?
    let excludedFraction: Double
    let pixels: Int

    nonisolated var json: JSONValue {
        .object(["rgb_all": rgbAll.map { .array($0.map { .number(Double($0)) }) } ?? .null,
                 "rgb_trim": rgbTrim.map { .array($0.map { .number(Double($0)) }) } ?? .null,
                 "excluded_fraction": .number(excludedFraction), "pixels": .number(Double(pixels))])
    }
}

enum Regions {
    nonisolated static func hasAllSixMeasured(_ sample: [String: JSONValue]) -> Bool {
        guard case .object(let values) = sample["regions"] else { return false }
        return ["forehead", "left_cheek", "right_cheek", "nose", "chin", "background"].allSatisfy { name in
            guard case .object(let stat) = values[name], case .number(let pixels) = stat["pixels"], pixels > 0,
                  case .array(let rgb) = stat["rgb_all"] else { return false }
            return rgb.count == 3
        }
    }

    // Same bounding-box definition as Android; not landmarks, not a verdict.
    nonisolated static let skin: [(String, CGRect)] = [
        ("forehead", CGRect(x: 0.30, y: 0.06, width: 0.40, height: 0.16)),
        ("left_cheek", CGRect(x: 0.14, y: 0.50, width: 0.22, height: 0.18)),
        ("right_cheek", CGRect(x: 0.64, y: 0.50, width: 0.22, height: 0.18)),
        ("nose", CGRect(x: 0.43, y: 0.42, width: 0.14, height: 0.20)),
        ("chin", CGRect(x: 0.38, y: 0.86, width: 0.24, height: 0.11))
    ]

    nonisolated static func skinBoxes(face: CGRect) -> [(String, CGRect)] {
        skin.map { name, f in (name, CGRect(x: face.minX + f.minX * face.width, y: face.minY + f.minY * face.height,
                                           width: f.width * face.width, height: f.height * face.height)) }
    }

    nonisolated static func backgroundBoxes(face: CGRect, width: Int, height: Int) -> [CGRect] {
        let side = Double(width) * 0.12
        let margin = face.insetBy(dx: -face.width * 0.1, dy: -face.height * 0.1)
        return [CGRect(x: 0, y: 0, width: side, height: side),
                CGRect(x: Double(width) - side, y: 0, width: side, height: side)]
            .filter { $0.maxY <= Double(height) && !$0.intersects(margin) }
    }

    nonisolated static func measure(_ buffer: CVPixelBuffer, box: CGRect, hostMs: Double) -> [String: JSONValue]? {
        guard hostMs.isFinite, [box.minX, box.minY, box.width, box.height].allSatisfy(\.isFinite),
              box.width > 0, box.height > 0,
              CVPixelBufferGetPixelFormatType(buffer) == kCVPixelFormatType_32BGRA,
              CVPixelBufferLockBaseAddress(buffer, .readOnly) == kCVReturnSuccess else { return nil }
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        guard let base = CVPixelBufferGetBaseAddress(buffer) else { return nil }
        let width = CVPixelBufferGetWidth(buffer), height = CVPixelBufferGetHeight(buffer)
        let rowBytes = CVPixelBufferGetBytesPerRow(buffer)
        guard width > 0, height > 0, rowBytes >= width * 4 else { return nil }
        let face = CGRect(x: box.minX * Double(width), y: box.minY * Double(height),
                          width: box.width * Double(width), height: box.height * Double(height))
        let bytes = base.assumingMemoryBound(to: UInt8.self)
        var result: [String: JSONValue] = [:]
        for (name, rect) in skinBoxes(face: face) {
            result[name] = stat(boxes: [rect], width: width, height: height, rowBytes: rowBytes, bytes: bytes).json
        }
        let backgrounds = backgroundBoxes(face: face, width: width, height: height)
        // Keep the background key even if no safe square exists: report missing,
        // never substitute a patch containing the face.
        result["background"] = stat(boxes: backgrounds, width: width, height: height, rowBytes: rowBytes, bytes: bytes).json
        return ["t_ms": .number(hostMs), "regions": .object(result)]
    }

    nonisolated private static func stat(boxes: [CGRect], width: Int, height: Int, rowBytes: Int,
                                        bytes: UnsafePointer<UInt8>) -> RegionStat {
        var all = [[Int]](repeating: [Int](repeating: 0, count: 256), count: 3)
        var kept = all
        var n = 0, k = 0
        for box in boxes {
            let x0 = min(width, max(0, Int(box.minX))), x1 = min(width, max(0, Int(box.maxX)))
            let y0 = min(height, max(0, Int(box.minY))), y1 = min(height, max(0, Int(box.maxY)))
            guard x0 < x1, y0 < y1 else { continue }
            for y in stride(from: y0, to: y1, by: 3) {
                for x in stride(from: x0, to: x1, by: 3) {
                    let offset = y * rowBytes + x * 4
                    let r = Int(bytes[offset + 2]), g = Int(bytes[offset + 1]), b = Int(bytes[offset])
                    all[0][r] += 1; all[1][g] += 1; all[2][b] += 1; n += 1
                    let luma = 0.299 * Double(r) + 0.587 * Double(g) + 0.114 * Double(b)
                    if luma > 55 && luma < 200 {
                        kept[0][r] += 1; kept[1][g] += 1; kept[2][b] += 1; k += 1
                    }
                }
            }
        }
        return RegionStat(rgbAll: n == 0 ? nil : all.map { median($0, count: n) },
                          rgbTrim: k == 0 ? nil : kept.map { median($0, count: k) },
                          excludedFraction: n == 0 ? 0 : 1 - Double(k) / Double(n), pixels: n)
    }

    nonisolated static func median(_ histogram: [Int], count: Int) -> Int {
        var sum = 0, low: Int?
        for value in histogram.indices {
            sum += histogram[value]
            if low == nil && sum > (count - 1) / 2 { low = value }
            if sum > count / 2 { return ((low ?? value) + value + 1) / 2 }
        }
        return 0
    }
}
