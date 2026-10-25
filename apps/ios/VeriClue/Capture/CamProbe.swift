import CoreVideo
import Darwin
import Foundation
import UIKit

struct DuplicateFrameMeter: Sendable {
    private var last: [UInt8]?
    private(set) var pairs = 0
    private var same = 0

    nonisolated init() {}

    nonisolated mutating func add(_ thumb: [UInt8]) {
        guard thumb.count == 24 * 24, pairs < 30 else { return }
        if let last { pairs += 1; if last == thumb { same += 1 } }
        last = thumb
    }

    nonisolated var ratio: Double? { pairs == 0 ? nil : Double(same) / Double(pairs) }

    nonisolated static func thumbnail(_ buffer: CVPixelBuffer) -> [UInt8]? {
        guard CVPixelBufferGetPixelFormatType(buffer) == kCVPixelFormatType_32BGRA,
              CVPixelBufferLockBaseAddress(buffer, .readOnly) == kCVReturnSuccess else { return nil }
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        guard let address = CVPixelBufferGetBaseAddress(buffer) else { return nil }
        let width = CVPixelBufferGetWidth(buffer), height = CVPixelBufferGetHeight(buffer)
        let row = CVPixelBufferGetBytesPerRow(buffer)
        guard width > 0, height > 0, row >= width * 4 else { return nil }
        let bytes = address.assumingMemoryBound(to: UInt8.self)
        var thumb = [UInt8](repeating: 0, count: 24 * 24)
        for i in thumb.indices {
            let offset = (i / 24 * height / 24) * row + (i % 24 * width / 24) * 4
            let blue = Double(bytes[offset]) * 0.114
            let green = Double(bytes[offset + 1]) * 0.587
            let red = Double(bytes[offset + 2]) * 0.299
            thumb[i] = UInt8(min(255, max(0, Int((blue + green + red).rounded()))))
        }
        return thumb
    }
}

enum DeviceProbe {
    static func collect() -> CamProbe {
        var flags: [String] = []
        var probes: [[String: JSONValue]] = []
        #if targetEnvironment(simulator)
        flags.append("ios:simulator")
        probes.append(["probe": .string("jailbreak"), "status": .string("skipped_simulator")])
        #else
        let paths = ["/Applications/Cydia.app", "/bin/bash", "/usr/sbin/sshd", "/etc/apt", "/var/jb"]
        let found = paths.filter { FileManager.default.fileExists(atPath: $0) }
        // Unique, exclusively-created probe, never overwrite another app/user's file.
        let url = URL(fileURLWithPath: "/private/vericlue-jb-probe-\(UUID().uuidString)")
        var wroteOutsideSandbox = false
        do {
            try Data("probe".utf8).write(to: url, options: .withoutOverwriting)
            wroteOutsideSandbox = true
            try? FileManager.default.removeItem(at: url)
        } catch { /* Expected in the iOS sandbox, not proof of device integrity. */ }
        if !found.isEmpty || wroteOutsideSandbox { flags.append("ios:jailbreak") }
        probes.append(["probe": .string("jailbreak"), "path_indicators": .array(found.map { .string($0) }),
                       "outside_sandbox_write": .bool(wroteOutsideSandbox)])
        #endif
        #if DEBUG
        probes.append(["probe": .string("debugger"), "status": .string("skipped_debug_build")])
        #else
        var info = kinfo_proc()
        var length = MemoryLayout<kinfo_proc>.stride
        var mib: [Int32] = [CTL_KERN, KERN_PROC, KERN_PROC_PID, getpid()]
        let result = sysctl(&mib, u_int(mib.count), &info, &length, nil, 0)
        let traced = result == 0 && (info.kp_proc.p_flag & P_TRACED) != 0
        if traced { flags.append("ios:debugger") }
        probes.append(["probe": .string("debugger"), "status": .string(result == 0 ? "checked" : "unavailable"),
                       "traced": result == 0 ? .bool(traced) : .null])
        #endif
        var system = utsname()
        uname(&system)
        let machine = withUnsafeBytes(of: &system.machine) { raw -> String in
            String(bytes: raw.prefix { $0 != 0 }, encoding: .utf8) ?? "unknown"
        }
        return CamProbe(apiTamperFlags: flags, constraintProbes: probes,
                        deviceLabel: "\(UIDevice.current.model) \(machine) · camera front")
    }

    static var debuggerNote: String {
        #if DEBUG
        "skipped_debug_build"
        #else
        "release_sysctl_P_TRACED"
        #endif
    }
}
