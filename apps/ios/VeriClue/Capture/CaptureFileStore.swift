import Foundation

// Only capture-owned UUID files. Never sweep all WAV/MP4 in shared tmp.
enum CaptureFileStore {
    nonisolated private static let lock = NSLock()
    nonisolated(unsafe) private static var leased: Set<URL> = []
    nonisolated static var directory: URL {
        FileManager.default.temporaryDirectory.appendingPathComponent("vericlue-capture", isDirectory: true)
    }

    nonisolated static func makeVideoURL(voice: Bool) throws -> URL {
        let root = directory
        if FileManager.default.fileExists(atPath: root.path),
           try root.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink == true { throw VideoWriterError.storage }
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let url = root.appendingPathComponent("\(voice ? "voice" : "face")-\(UUID().uuidString).mp4")
        lock.lock(); leased.insert(url.standardizedFileURL); lock.unlock()
        return url
    }

    nonisolated static func release(_ url: URL) {
        lock.lock(); leased.remove(url.standardizedFileURL); lock.unlock()
    }

    @discardableResult
    nonisolated static func cleanupOrphans() -> Int {
        cleanup(directory, legacy: false) + cleanup(FileManager.default.temporaryDirectory, legacy: true)
    }

    nonisolated static func ownedFileCount() -> Int {
        [(directory, false), (FileManager.default.temporaryDirectory, true)].reduce(0) { count, item in
            guard let files = try? FileManager.default.contentsOfDirectory(at: item.0,
                includingPropertiesForKeys: [.isRegularFileKey, .isSymbolicLinkKey]) else { return count }
            return count + files.filter { file in
                guard ownsName(file.lastPathComponent, legacy: item.1),
                      let values = try? file.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey]) else { return false }
                return values.isRegularFile == true && values.isSymbolicLink != true
            }.count
        }
    }

    @discardableResult
    nonisolated static func cleanup(_ root: URL, legacy: Bool) -> Int {
        guard (try? root.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink) != true,
              let files = try? FileManager.default.contentsOfDirectory(at: root,
                  includingPropertiesForKeys: [.isRegularFileKey, .isSymbolicLinkKey]) else { return 0 }
        lock.lock(); defer { lock.unlock() }
        var removed = 0
        for file in files {
            guard !leased.contains(file.standardizedFileURL), ownsName(file.lastPathComponent, legacy: legacy),
                  let values = try? file.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey]),
                  values.isRegularFile == true, values.isSymbolicLink != true else { continue }
            do { try FileManager.default.removeItem(at: file); removed += 1 } catch { /* Retry next launch. */ }
        }
        return removed
    }

    nonisolated static func ownsName(_ name: String, legacy: Bool) -> Bool {
        let url = URL(fileURLWithPath: name)
        guard ["mp4", "wav"].contains(url.pathExtension) else { return false }
        let stem = url.deletingPathExtension().lastPathComponent
        let prefixes = legacy ? ["vericlue-face-", "vericlue-voice-"] : ["face-", "voice-"]
        return prefixes.contains { prefix in
            stem.hasPrefix(prefix) && UUID(uuidString: String(stem.dropFirst(prefix.count))) != nil
        }
    }
}
