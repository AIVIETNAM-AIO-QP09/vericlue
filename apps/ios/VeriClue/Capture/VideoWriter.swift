import AVFoundation
import CoreGraphics
import CoreMedia
import CoreVideo
import Foundation

enum VideoWriterError: Error, Sendable, Equatable {
    case alreadyRecording, notRecording, qualityLost, invalidSample, unsupportedFormat
    case cannotStart, cannotAppend, cannotFinish, noFrames, cancelled, tooLong, invalidOutput, storage, frameGap
}

enum VideoWriterPhase: String, Sendable { case idle, armed, writing, finishing, finished, failed }

struct VideoFrameClock: Sendable {
    // Local capture-integrity guard, not a server/model threshold. Allow up to
    // three 30fps intervals (plus rounding); never hide a stall by retiming frames.
    nonisolated static let maximumFrameGap = 0.100001
    private(set) var firstPTS: CMTime?
    private(set) var lastPTS: CMTime?
    private(set) var frameTimes: [FrameTime] = []

    nonisolated init() {
        firstPTS = nil
        lastPTS = nil
        frameTimes = []
    }

    nonisolated var elapsed: Double {
        guard let firstPTS, let lastPTS else { return 0 }
        return CMTimeSubtract(lastPTS, firstPTS).seconds
    }

    nonisolated func validate(_ pts: CMTime) throws {
        guard pts.isValid, pts.timescale > 0, pts.seconds.isFinite else { throw VideoWriterError.invalidSample }
        if let firstPTS, pts.epoch != firstPTS.epoch { throw VideoWriterError.invalidSample }
        if let lastPTS, CMTimeCompare(pts, lastPTS) <= 0 { throw VideoWriterError.invalidSample }
        if let firstPTS, CMTimeSubtract(pts, firstPTS).seconds > 60 { throw VideoWriterError.tooLong }
        if let lastPTS, CMTimeSubtract(pts, lastPTS).seconds > Self.maximumFrameGap {
            throw VideoWriterError.frameGap
        }
    }

    nonisolated mutating func accepted(_ pts: CMTime) throws {
        try validate(pts)
        if firstPTS == nil { firstPTS = pts }
        lastPTS = pts
        frameTimes.append(FrameTime(captureTime: pts.seconds * 1000, presentedFrames: frameTimes.count + 1,
            mediaTime: CMTimeSubtract(pts, firstPTS ?? pts).seconds))
    }
}

struct RecordedVideo: Sendable {
    let url: URL
    let firstPTS: CMTime
    let lastPTS: CMTime
    let frameTimes: [FrameTime]
    let width: Int
    let height: Int
    let backpressureDrops: Int
}

struct VideoRecordingSnapshot: Sendable {
    let phase: VideoWriterPhase
    let frames: Int
    let elapsed: Double
    let backpressureDrops: Int
    let failure: VideoWriterError?
    let firstPTSSeconds: Double?
}

// All synchronous methods must run on the SAME serial queue as the camera samples.
// finish() hops onto that queue before marking input finished, then awaits AVFoundation.
final class VideoWriter: @unchecked Sendable {
    nonisolated private let queue: DispatchQueue
    nonisolated(unsafe) private var writer: AVAssetWriter?
    nonisolated(unsafe) private var input: AVAssetWriterInput?
    nonisolated(unsafe) private var phase = VideoWriterPhase.idle
    nonisolated(unsafe) private var failure: VideoWriterError?
    nonisolated(unsafe) private var url: URL?
    nonisolated(unsafe) private var ownsFile = false
    nonisolated(unsafe) private var recordingID = UUID()
    nonisolated(unsafe) private var clock = VideoFrameClock()
    nonisolated(unsafe) private var width = 0
    nonisolated(unsafe) private var height = 0
    nonisolated(unsafe) private var backpressureDrops = 0
    nonisolated(unsafe) private var finishWaiter: CheckedContinuation<RecordedVideo, Error>?

    nonisolated init(queue: DispatchQueue) { self.queue = queue }

    nonisolated var snapshot: VideoRecordingSnapshot {
        dispatchPrecondition(condition: .onQueue(queue))
        return VideoRecordingSnapshot(phase: phase, frames: clock.frameTimes.count, elapsed: clock.elapsed,
            backpressureDrops: backpressureDrops, failure: failure, firstPTSSeconds: clock.firstPTS?.seconds)
    }

    nonisolated func start(url: URL, format: CMFormatDescription? = nil) throws {
        dispatchPrecondition(condition: .onQueue(queue))
        guard ![.armed, .writing, .finishing].contains(phase) else { throw VideoWriterError.alreadyRecording }
        // Never overwrite/delete an existing file supplied by a caller.
        guard url.isFileURL, !FileManager.default.fileExists(atPath: url.path) else { throw VideoWriterError.storage }
        cancel(preserveCompleted: false)
        do {
            writer = try AVAssetWriter(outputURL: url, fileType: .mp4)
            writer?.shouldOptimizeForNetworkUse = true
        } catch { throw VideoWriterError.storage }
        self.url = url
        ownsFile = true
        recordingID = UUID()
        clock = VideoFrameClock()
        backpressureDrops = 0
        failure = nil
        phase = .armed
        // The camera supplies its current format before recording starts. Expensive
        // writer setup must not happen after choosing the first recorded frame/t0.
        if let format {
            do { try configure(format) }
            catch {
                let reason = (error as? VideoWriterError) ?? .cannotStart
                fail(reason)
                throw reason
            }
        }
    }

    nonisolated func append(_ sample: CMSampleBuffer, mirrored: Bool, portrait: Bool) {
        dispatchPrecondition(condition: .onQueue(queue))
        guard phase == .armed || phase == .writing else { return }
        do {
            guard !mirrored, portrait, CMSampleBufferDataIsReady(sample),
                  let pixels = CMSampleBufferGetImageBuffer(sample),
                  CVPixelBufferGetPixelFormatType(pixels) == kCVPixelFormatType_32BGRA else {
                throw VideoWriterError.unsupportedFormat
            }
            let pts = CMSampleBufferGetPresentationTimeStamp(sample)
            try clock.validate(pts)
            if input == nil {
                guard let format = CMSampleBufferGetFormatDescription(sample) else { throw VideoWriterError.unsupportedFormat }
                try configure(format)
                // Setup may block. Use a fresh frame on the next callback, not this
                // now-stale sample. Production preconfigures in start(url:format:).
                return
            }
            guard let writer, writer.status == .writing, let input,
                  CVPixelBufferGetWidth(pixels) == width, CVPixelBufferGetHeight(pixels) == height else {
                throw VideoWriterError.cannotAppend
            }
            guard input.isReadyForMoreMediaData else { backpressureDrops += 1; return }
            // No session/t0 is selected for discarded startup frames. Never keep
            // an old first frame and append a much later one after encoder warmup.
            if clock.firstPTS == nil { writer.startSession(atSourceTime: pts) }
            guard input.append(sample) else { throw VideoWriterError.cannotAppend }
            try clock.accepted(pts)
            phase = .writing
        } catch { fail((error as? VideoWriterError) ?? .cannotAppend) }
    }

    nonisolated private func configure(_ format: CMFormatDescription) throws {
        guard let writer else { throw VideoWriterError.cannotStart }
        guard CMFormatDescriptionGetMediaType(format) == kCMMediaType_Video,
              CMFormatDescriptionGetMediaSubType(format) == kCVPixelFormatType_32BGRA else {
            throw VideoWriterError.unsupportedFormat
        }
        let dimensions = CMVideoFormatDescriptionGetDimensions(format)
        width = Int(dimensions.width)
        height = Int(dimensions.height)
        guard height > width, width > 0, width.isMultiple(of: 2), height.isMultiple(of: 2) else {
            throw VideoWriterError.unsupportedFormat
        }
        let settings: [String: Any] = [AVVideoCodecKey: AVVideoCodecType.h264,
            AVVideoWidthKey: width, AVVideoHeightKey: height,
            AVVideoCompressionPropertiesKey: [AVVideoAverageBitRateKey: 3_000_000,
                AVVideoExpectedSourceFrameRateKey: 30, AVVideoMaxKeyFrameIntervalKey: 30,
                AVVideoAllowFrameReorderingKey: false, AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel]]
        guard writer.canApply(outputSettings: settings, forMediaType: .video) else { throw VideoWriterError.unsupportedFormat }
        let input = AVAssetWriterInput(mediaType: .video, outputSettings: settings,
            sourceFormatHint: format)
        input.expectsMediaDataInRealTime = true
        input.transform = .identity // Pixels already portrait/unmirrored. Do not rotate twice.
        guard writer.canAdd(input) else { throw VideoWriterError.cannotStart }
        writer.add(input)
        self.input = input
        guard writer.startWriting() else { throw VideoWriterError.cannotStart }
    }

    nonisolated func finish() async throws -> RecordedVideo {
        try await withCheckedThrowingContinuation { continuation in
            queue.async { self.finishOnQueue(continuation) }
        }
    }

    nonisolated private func finishOnQueue(_ continuation: CheckedContinuation<RecordedVideo, Error>) {
        dispatchPrecondition(condition: .onQueue(queue))
        guard phase == .writing || phase == .armed else {
            continuation.resume(throwing: failure ?? .notRecording)
            return
        }
        guard let writer, let input, clock.firstPTS != nil, clock.lastPTS != nil else {
            fail(.noFrames)
            continuation.resume(throwing: VideoWriterError.noFrames)
            return
        }
        guard writer.status == .writing else {
            fail(.cannotFinish)
            continuation.resume(throwing: VideoWriterError.cannotFinish)
            return
        }
        phase = .finishing
        finishWaiter = continuation
        let id = recordingID
        input.markAsFinished()
        writer.finishWriting { [self] in
            queue.async { [self] in
                guard recordingID == id, phase == .finishing, let waiter = finishWaiter else { return }
                guard self.writer?.status == .completed, let url, let first = clock.firstPTS, let last = clock.lastPTS else {
                    fail(.cannotFinish)
                    return
                }
                phase = .finished
                finishWaiter = nil
                waiter.resume(returning: RecordedVideo(url: url, firstPTS: first, lastPTS: last,
                    frameTimes: clock.frameTimes, width: width, height: height, backpressureDrops: backpressureDrops))
            }
        }
    }

    nonisolated func cancel(preserveCompleted: Bool, reason: VideoWriterError = .cancelled) {
        dispatchPrecondition(condition: .onQueue(queue))
        if preserveCompleted && phase == .finished { return }
        let wasActive = [.armed, .writing, .finishing].contains(phase)
        if writer?.status == .writing { writer?.cancelWriting() }
        input = nil
        writer = nil
        if ownsFile, let url { try? FileManager.default.removeItem(at: url) }
        ownsFile = false
        url = nil
        clock = VideoFrameClock()
        width = 0
        height = 0
        backpressureDrops = 0
        let waiter = finishWaiter
        finishWaiter = nil
        phase = wasActive ? .failed : .idle
        failure = wasActive ? reason : nil
        waiter?.resume(throwing: reason)
    }

    nonisolated private func fail(_ error: VideoWriterError) {
        cancel(preserveCompleted: false, reason: error)
        phase = .failed
        failure = error
    }
}

struct VideoInspection: Sendable {
    let seconds: Double
    let width: Int
    let height: Int
    let bytes: Int64

    nonisolated static func inspect(_ video: RecordedVideo) async throws -> VideoInspection {
        let asset = AVURLAsset(url: video.url)
        let playable = try await asset.load(.isPlayable)
        let duration = try await asset.load(.duration).seconds
        let tracks = try await asset.loadTracks(withMediaType: .video)
        let audio = try await asset.loadTracks(withMediaType: .audio)
        guard playable, duration.isFinite, duration > 0, tracks.count == 1, audio.isEmpty, let track = tracks.first else {
            throw VideoWriterError.invalidOutput
        }
        let size = try await track.load(.naturalSize)
        let transform = try await track.load(.preferredTransform)
        let formats = try await track.load(.formatDescriptions)
        guard size.width == CGFloat(video.width), size.height == CGFloat(video.height), size.height > size.width,
              transform.isIdentity, let format = formats.first,
              CMFormatDescriptionGetMediaSubType(format) == kCMVideoCodecType_H264 else { throw VideoWriterError.invalidOutput }
        let attributes = try FileManager.default.attributesOfItem(atPath: video.url.path)
        guard let bytes = (attributes[.size] as? NSNumber)?.int64Value, bytes > 0 else { throw VideoWriterError.invalidOutput }
        return VideoInspection(seconds: duration, width: Int(size.width), height: Int(size.height), bytes: bytes)
    }
}
