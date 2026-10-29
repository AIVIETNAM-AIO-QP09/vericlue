import AVFoundation
import Combine
import Foundation

enum WavError: Error, Equatable, Sendable {
    case denied, unavailable, conversion, invalidClock, interrupted, empty, cancelled
}

struct WavRecording: Sendable {
    let data: Data
    let firstHostSeconds: Double
    let seconds: Double
    let peakRms: Double
}

enum WavPCM {
    nonisolated static let sampleRate = 16_000
    nonisolated static let maximumSamples = sampleRate * 8

    nonisolated static func encode(_ pcm: Data) throws -> Data {
        guard !pcm.isEmpty, pcm.count.isMultiple(of: 2), pcm.count <= maximumSamples * 2 else { throw WavError.empty }
        var result = Data()
        func text(_ value: String) { result.append(contentsOf: value.utf8) }
        func u16(_ value: UInt16) { var le = value.littleEndian; withUnsafeBytes(of: &le) { result.append(contentsOf: $0) } }
        func u32(_ value: UInt32) { var le = value.littleEndian; withUnsafeBytes(of: &le) { result.append(contentsOf: $0) } }
        text("RIFF"); u32(UInt32(36 + pcm.count)); text("WAVE")
        text("fmt "); u32(16); u16(1); u16(1); u32(16_000); u32(32_000); u16(2); u16(16)
        text("data"); u32(UInt32(pcm.count)); result.append(pcm)
        return result
    }

    nonisolated static func offsetMs(audioHost: Double, videoHost: Double) throws -> Int {
        let delta = (audioHost - videoHost) * 1000
        guard delta.isFinite, (0...3000).contains(delta) else { throw WavError.invalidClock }
        return Int(delta.rounded())
    }
}

struct WavMeter: Sendable {
    let level: Double
    let seconds: Double
    let firstHostSeconds: Double?
    let limitReached: Bool
    let failure: WavError?
}

// The tap and teardown may run concurrently. One lock owns converter + PCM;
// callbacks never retain/reuse the engine's input buffer after returning.
final class AudioPCMCollector: @unchecked Sendable {
    nonisolated private let lock = NSLock()
    nonisolated private let converter: AVAudioConverter
    nonisolated private let format: AVAudioFormat
    nonisolated(unsafe) private var pcm = Data()
    nonisolated(unsafe) private var firstHost: Double?
    nonisolated(unsafe) private var nextHost: Double?
    nonisolated(unsafe) private var peak = 0.0
    nonisolated(unsafe) private var audibleSamples = 0
    nonisolated(unsafe) private var failure: WavError?
    nonisolated(unsafe) private var closed = false

    nonisolated init(input: AVAudioFormat) throws {
        guard input.sampleRate > 0, input.channelCount > 0,
              let target = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16_000, channels: 1, interleaved: false),
              let converter = AVAudioConverter(from: input, to: target) else { throw WavError.unavailable }
        self.converter = converter; format = target
        converter.primeMethod = .none
        converter.downmix = true
    }

    nonisolated func consume(_ buffer: AVAudioPCMBuffer, at time: AVAudioTime) -> WavMeter {
        lock.lock(); defer { lock.unlock() }
        guard !closed, failure == nil, pcm.count < WavPCM.maximumSamples * 2 else { return meter(level: 0) }
        guard buffer.format == converter.inputFormat else { failure = .conversion; return meter(level: 0) }
        guard time.isHostTimeValid, buffer.frameLength > 0 else { failure = .invalidClock; return meter(level: 0) }
        let host = AVAudioTime.seconds(forHostTime: time.hostTime)
        guard host.isFinite, nextHost.map({ abs(host - $0) <= 0.1 }) ?? true else {
            failure = .invalidClock; return meter(level: 0)
        }
        nextHost = host + Double(buffer.frameLength) / buffer.format.sampleRate
        if firstHost == nil { firstHost = host }
        let capacity = AVAudioFrameCount(ceil(Double(buffer.frameLength) * 16_000 / buffer.format.sampleRate) + 64)
        guard let output = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: capacity) else {
            failure = .conversion; return meter(level: 0)
        }
        // AVAudioConverter calls this input block synchronously under our lock.
        // The wrapper never escapes this call or transfers the borrowed buffer.
        let input = ConverterInput(buffer)
        var error: NSError?
        let status = converter.convert(to: output, error: &error) { _, inputStatus in
            guard !input.supplied else { inputStatus.pointee = .noDataNow; return nil }
            input.supplied = true; inputStatus.pointee = .haveData; return input.buffer
        }
        guard error == nil, status != .error else { failure = .conversion; return meter(level: 0) }
        return meter(level: append(output))
    }

    nonisolated private func append(_ buffer: AVAudioPCMBuffer) -> Double {
        let n = min(Int(buffer.frameLength), WavPCM.maximumSamples - pcm.count / 2)
        guard n > 0, let samples = buffer.int16ChannelData?[0] else { return 0 }
        var energy = 0.0
        for i in 0..<n { let s = Double(samples[i]) / 32768; energy += s * s }
        let rms = sqrt(energy / Double(n))
        peak = max(peak, rms)
        // A local silence heuristic, not a speech/content verification verdict.
        if rms >= 0.005 { audibleSamples += n }
        pcm.append(UnsafeBufferPointer(start: UnsafeRawPointer(samples).assumingMemoryBound(to: UInt8.self), count: n * 2))
        return min(1, rms * 4)
    }

    nonisolated private func meter(level: Double) -> WavMeter {
        WavMeter(level: level, seconds: Double(pcm.count) / 32_000, firstHostSeconds: firstHost,
                 limitReached: pcm.count >= WavPCM.maximumSamples * 2, failure: failure)
    }

    nonisolated func finish() throws -> WavRecording {
        lock.lock(); defer { lock.unlock() }
        guard !closed else { throw WavError.cancelled }
        closed = true
        defer { pcm = Data() }
        if let failure { throw failure }
        guard firstHost != nil, !pcm.isEmpty else { throw WavError.empty }
        // Flush the resampler before sealing the header/data lengths.
        guard let output = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: 2048) else { throw WavError.conversion }
        var error: NSError?
        let status = converter.convert(to: output, error: &error) { _, inputStatus in
            inputStatus.pointee = .endOfStream; return nil
        }
        guard error == nil, status != .error else { throw WavError.conversion }
        _ = append(output)
        guard let firstHost, audibleSamples >= 2400 else { throw WavError.empty }
        return WavRecording(data: try WavPCM.encode(pcm), firstHostSeconds: firstHost,
                            seconds: Double(pcm.count) / 32_000, peakRms: peak)
    }
}

private final class ConverterInput: @unchecked Sendable {
    nonisolated(unsafe) let buffer: AVAudioPCMBuffer
    nonisolated(unsafe) var supplied = false
    nonisolated init(_ buffer: AVAudioPCMBuffer) { self.buffer = buffer }
}

private final class WavWorker: @unchecked Sendable {
    nonisolated private let queue = DispatchQueue(label: "vn.vericlue.voice-audio", qos: .userInitiated)
    nonisolated(unsafe) private var engine: AVAudioEngine?
    nonisolated(unsafe) private var collector: AudioPCMCollector?
    nonisolated(unsafe) private var tapped = false
    nonisolated(unsafe) private var oldCategory: AVAudioSession.Category?
    nonisolated(unsafe) private var oldMode: AVAudioSession.Mode?
    nonisolated(unsafe) private var oldOptions: AVAudioSession.CategoryOptions = []
    nonisolated(unsafe) private var oldInput: AVAudioSessionPortDescription?

    nonisolated func prepare() async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            queue.async {
                do {
                    self.teardown()
                    let session = AVAudioSession.sharedInstance()
                    self.oldCategory = session.category; self.oldMode = session.mode
                    self.oldOptions = session.categoryOptions; self.oldInput = session.preferredInput
                    try session.setCategory(.playAndRecord, mode: .measurement, options: .defaultToSpeaker)
                    try session.setActive(true)
                    guard let mic = session.availableInputs?.first(where: { $0.portType == .builtInMic }) else { throw WavError.unavailable }
                    try session.setPreferredInput(mic)
                    let engine = AVAudioEngine()
                    self.engine = engine
                    self.collector = try AudioPCMCollector(input: engine.inputNode.outputFormat(forBus: 0))
                    continuation.resume()
                } catch { self.teardown(); continuation.resume(throwing: error) }
            }
        }
    }

    nonisolated func start(observer: @escaping @Sendable (WavMeter) -> Void) async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            queue.async {
                do {
                    guard let engine = self.engine, let collector = self.collector, !self.tapped else { throw WavError.unavailable }
                    engine.inputNode.installTap(onBus: 0, bufferSize: 1024, format: nil) { buffer, time in
                        observer(collector.consume(buffer, at: time))
                    }
                    self.tapped = true
                    engine.prepare()
                    try engine.start()
                    continuation.resume()
                } catch { self.teardown(); continuation.resume(throwing: error) }
            }
        }
    }

    nonisolated func finish() async throws -> WavRecording {
        try await withCheckedThrowingContinuation { continuation in
            queue.async {
                do {
                    self.stopEngine()
                    guard let collector = self.collector else { throw WavError.empty }
                    let result = try collector.finish()
                    self.teardown(); continuation.resume(returning: result)
                } catch { self.teardown(); continuation.resume(throwing: error) }
            }
        }
    }

    nonisolated func cancel() { queue.async { self.teardown() } }

    nonisolated private func stopEngine() {
        engine?.stop()
        if tapped { engine?.inputNode.removeTap(onBus: 0); tapped = false }
    }

    nonisolated private func teardown() {
        stopEngine(); collector = nil; engine = nil
        guard let oldCategory, let oldMode else { return }
        let session = AVAudioSession.sharedInstance()
        try? session.setActive(false, options: .notifyOthersOnDeactivation)
        try? session.setCategory(oldCategory, mode: oldMode, options: oldOptions)
        try? session.setPreferredInput(oldInput)
        self.oldCategory = nil; self.oldMode = nil; oldInput = nil
    }
}

@MainActor
final class WavRecorder: ObservableObject {
    @Published private(set) var meter = WavMeter(level: 0, seconds: 0, firstHostSeconds: nil, limitReached: false, failure: nil)
    private let worker = WavWorker()
    private var generation = 0

    func prepare() async throws {
        generation += 1
        let id = generation
        let allowed = await AVCaptureDevice.requestAccess(for: .audio)
        guard id == generation, !Task.isCancelled else { throw WavError.cancelled }
        guard allowed else { throw WavError.denied }
        meter = WavMeter(level: 0, seconds: 0, firstHostSeconds: nil, limitReached: false, failure: nil)
        try await worker.prepare()
        guard id == generation, !Task.isCancelled else { throw WavError.cancelled }
    }

    func start() async throws {
        let id = generation
        try await worker.start { [weak self] value in
            Task { @MainActor [weak self] in guard let self, id == self.generation else { return }; self.meter = value }
        }
        guard id == generation, !Task.isCancelled else { throw WavError.cancelled }
    }

    func finish() async throws -> WavRecording {
        generation += 1 // Ignore tap callbacks queued before engine.stop().
        return try await worker.finish()
    }

    func cancel() { generation += 1; worker.cancel() }
}
