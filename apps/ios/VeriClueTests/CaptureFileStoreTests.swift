import Foundation
import Testing
@testable import VeriClue

@MainActor
struct CaptureFileStoreTests {
    @Test func cleanupOnlyRemovesOwnedRegularUuidFiles() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent("ios06-synthetic-\(UUID().uuidString)", isDirectory: true)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }
        let owned = ["face-\(UUID().uuidString).mp4", "voice-\(UUID().uuidString).wav"]
        let keep = ["unrelated.wav", "voice-not-a-uuid.mp4", "notes.txt"]
        for name in owned + keep { try Data("synthetic".utf8).write(to: root.appendingPathComponent(name), options: .withoutOverwriting) }
        let directory = root.appendingPathComponent("face-\(UUID().uuidString).mp4", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false)
        let link = root.appendingPathComponent("voice-\(UUID().uuidString).mp4")
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: root.appendingPathComponent("unrelated.wav"))
        #expect(CaptureFileStore.cleanup(root, legacy: false) == 2)
        for name in owned { #expect(!FileManager.default.fileExists(atPath: root.appendingPathComponent(name).path)) }
        for name in keep { #expect(FileManager.default.fileExists(atPath: root.appendingPathComponent(name).path)) }
        #expect(FileManager.default.fileExists(atPath: directory.path))
        #expect(FileManager.default.fileExists(atPath: link.path))
    }

    @Test func leasedFileSurvivesSweepUntilOwnerReleasesIt() throws {
        let url = try CaptureFileStore.makeVideoURL(voice: true)
        defer { CaptureFileStore.release(url); try? FileManager.default.removeItem(at: url) }
        try Data("synthetic".utf8).write(to: url, options: .withoutOverwriting)
        CaptureFileStore.cleanup(CaptureFileStore.directory, legacy: false)
        #expect(FileManager.default.fileExists(atPath: url.path))
        CaptureFileStore.release(url)
        CaptureFileStore.cleanup(CaptureFileStore.directory, legacy: false)
        #expect(!FileManager.default.fileExists(atPath: url.path))
    }

    @Test func legacyMatchingNeverTreatsAllWavOrExportsAsOwned() {
        let id = UUID().uuidString
        #expect(CaptureFileStore.ownsName("vericlue-face-\(id).mp4", legacy: true))
        #expect(CaptureFileStore.ownsName("vericlue-voice-\(id).wav", legacy: true))
        #expect(!CaptureFileStore.ownsName("voice_audio.wav", legacy: true))
        #expect(!CaptureFileStore.ownsName("export.wav", legacy: true))
        #expect(!CaptureFileStore.ownsName("face-invalid.mp4", legacy: false))
        #expect(!CaptureFileStore.ownsName("voice-\(id).txt", legacy: false))
    }
}
