import AVFoundation
import Combine
import CoreMedia
import CoreVideo
import Foundation
import QuartzCore
import SwiftUI
import UIKit

enum FrontCameraError: Error {
    case denied, unavailable, unsupportedConfiguration, noFrames
}

// Metadata only. Never retain camera pixels in the checkpoint's diagnostics.
struct FrontCameraFrameMeter: Sendable {
    private(set) var frames = 0
    private(set) var droppedFrames = 0
    private(set) var width = 0
    private(set) var height = 0
    private(set) var fps = 0.0
    private var windowStart: Double?
    private var windowFrames = 0
    private var lastPublished: Double?

    nonisolated mutating func beginRun() {
        windowStart = nil
        windowFrames = 0
        lastPublished = nil
        fps = 0
    }

    nonisolated mutating func record(pts: Double, width: Int, height: Int) -> Bool {
        guard pts.isFinite, width > 0, height > 0 else { return false }
        frames += 1
        self.width = width
        self.height = height
        if let start = windowStart, pts >= start {
            windowFrames += 1
            let elapsed = pts - start
            if elapsed >= 0.5 {
                fps = Double(windowFrames - 1) / elapsed
                windowStart = pts
                windowFrames = 1
            }
        } else {
            windowStart = pts
            windowFrames = 1
        }
        if let lastPublished, pts >= lastPublished, pts - lastPublished < 0.5 { return false }
        lastPublished = pts
        return true
    }

    nonisolated mutating func dropped() { droppedFrames += 1 }
}

struct FrontCameraSnapshot: Sendable {
    let runID: Int
    let configurations: Int
    let inputs: Int
    let outputs: Int
    let meter: FrontCameraFrameMeter
    let mirrored: Bool
    let portrait: Bool
    let tracking: FaceTrackingResult?
    let quality: FaceQualityResult
    let recording: VideoRecordingSnapshot
    let firstHostSeconds: Double?
    let clockDeltaMs: Double?
    var recordingID: UUID? = nil
}

// This queue owns the session graph and all sample callbacks. No graph mutations on UI.
private final class FrontCameraWorker: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate, @unchecked Sendable {
    nonisolated(unsafe) let session = AVCaptureSession()
    nonisolated(unsafe) let output = AVCaptureVideoDataOutput()
    nonisolated private let queue: DispatchQueue
    nonisolated private let videoWriter: VideoWriter
    nonisolated(unsafe) private var configured = false
    nonisolated(unsafe) private var configurationCount = 0
    nonisolated(unsafe) private var runID = 0
    nonisolated(unsafe) private var meter = FrontCameraFrameMeter()
    nonisolated private let tracker = FaceTracker()
    nonisolated(unsafe) private var tracking: FaceTrackingResult?
    nonisolated(unsafe) private var gate = QualityGate()
    nonisolated(unsafe) private var quality = FaceQualityResult(state: .noFace, heldMs: 0, ready: false)
    nonisolated(unsafe) private var observer: (@Sendable (FrontCameraSnapshot) -> Void)?
    nonisolated(unsafe) private var latestFormat: CMFormatDescription?
    nonisolated(unsafe) private var device: AVCaptureDevice?
    nonisolated(unsafe) private var timeline: FaceTimeline?
    nonisolated(unsafe) private var firstHostSeconds: Double?
    nonisolated(unsafe) private var clockDeltaMs: Double?
    nonisolated(unsafe) private var hostFrameTimes: [FrameTime] = []
    nonisolated(unsafe) private var regions: [[String: JSONValue]] = []
    nonisolated(unsafe) private var duplicates = DuplicateFrameMeter()
    nonisolated(unsafe) private var frontalTask: Task<Data?, Never>?
    nonisolated(unsafe) private var frontalAtMs: Double?
    nonisolated(unsafe) private var baselineDone = false
    nonisolated(unsafe) private var colorsDone = false
    nonisolated(unsafe) private var aeAwbLocked = false
    nonisolated(unsafe) private var captureComplete = false
    nonisolated(unsafe) private var exposureLockedAtMs: Double?
    nonisolated(unsafe) private var exposureUnlockedAtMs: Double?
    nonisolated(unsafe) private var autoRestored = false
    nonisolated(unsafe) private var firstReceiptHostSeconds: Double?
    nonisolated(unsafe) private var recordingID: UUID?

    override init() {
        let queue = DispatchQueue(label: "vn.vericlue.front-camera", qos: .userInitiated)
        self.queue = queue
        videoWriter = VideoWriter(queue: queue)
        super.init()
    }

    nonisolated func start(runID: Int, observer: @escaping @Sendable (FrontCameraSnapshot) -> Void) async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            queue.async {
                do {
                    try self.configureOnce()
                    self.runID = runID
                    self.observer = observer
                    self.meter.beginRun()
                    self.tracking = nil
                    self.latestFormat = nil
                    self.gate.reset()
                    self.quality = FaceQualityResult(state: .noFace, heldMs: 0, ready: false)
                    if !self.session.isRunning { self.session.startRunning() }
                    guard self.session.isRunning else { throw FrontCameraError.unavailable }
                    continuation.resume()
                } catch { continuation.resume(throwing: error) }
            }
        }
    }

    nonisolated private func configureOnce() throws {
        guard !configured else { return }
        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .front) else {
            throw FrontCameraError.unavailable
        }
        let input = try AVCaptureDeviceInput(device: device)
        self.device = device
        guard session.canSetSessionPreset(.hd1280x720), session.canAddInput(input), session.canAddOutput(output) else {
            throw FrontCameraError.unsupportedConfiguration
        }
        session.beginConfiguration()
        defer {
            if !configured {
                if session.outputs.contains(where: { $0 === output }) { session.removeOutput(output) }
                if session.inputs.contains(where: { $0 === input }) { session.removeInput(input) }
            }
            session.commitConfiguration()
        }
        session.sessionPreset = .hd1280x720
        // Audio belongs to AVAudioEngine in IOS-05, not this video-only graph.
        session.automaticallyConfiguresApplicationAudioSession = false
        output.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
        output.alwaysDiscardsLateVideoFrames = true
        output.setSampleBufferDelegate(self, queue: queue)
        session.addInput(input)
        session.addOutput(output)
        guard let connection = output.connection(with: .video), connection.isVideoOrientationSupported,
              connection.isVideoMirroringSupported else {
            throw FrontCameraError.unsupportedConfiguration
        }
        connection.videoOrientation = .portrait
        connection.automaticallyAdjustsVideoMirroring = false
        connection.isVideoMirrored = false
        // Prefer 30fps if supported; actual frame rate is measured from sample PTS.
        if device.activeFormat.videoSupportedFrameRateRanges.contains(where: { $0.minFrameRate <= 30 && $0.maxFrameRate >= 30 }) {
            try device.lockForConfiguration()
            device.activeVideoMinFrameDuration = CMTime(value: 1, timescale: 30)
            device.activeVideoMaxFrameDuration = CMTime(value: 1, timescale: 30)
            device.unlockForConfiguration()
        }
        configured = true
        configurationCount += 1
    }

    nonisolated func stop() {
        queue.async {
            self.observer = nil
            self.latestFormat = nil
            self.videoWriter.cancel(preserveCompleted: true)
            self.restoreAutoExposure()
            self.clearEvidence()
            if self.session.isRunning { self.session.stopRunning() }
        }
    }

    nonisolated func startRecording(runID: Int, timeline: FaceTimeline?, forVoice: Bool, attemptID: UUID) async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            queue.async {
                do {
                    guard self.runID == runID, self.session.isRunning, (forVoice || self.quality.ready),
                          let format = self.latestFormat else { throw VideoWriterError.qualityLost }
                    let prefix = forVoice ? "voice" : "face"
                    let url = FileManager.default.temporaryDirectory.appendingPathComponent("vericlue-\(prefix)-\(UUID().uuidString).mp4")
                    self.clearEvidence()
                    self.recordingID = attemptID
                    self.restoreAutoExposure()
                    self.timeline = timeline
                    try self.videoWriter.start(url: url, format: format)
                    continuation.resume()
                } catch { continuation.resume(throwing: error) }
            }
        }
    }

    nonisolated func finishRecording() async throws -> RecordedVideo {
        let result = try await videoWriter.finish()
        await withCheckedContinuation { continuation in
            queue.async { self.restoreAutoExposure(); continuation.resume() }
        }
        return result
    }

    nonisolated func evidence() async throws -> FaceEvidence {
        let partial: (Task<Data?, Never>?, [FrameTime], [[String: JSONValue]], Double?, Bool, Double?, Double?, Double?, [String: JSONValue]) =
            await withCheckedContinuation { continuation in
                queue.async {
                    let diagnostic: [String: JSONValue] = [
                        "ae_lock_at_ms": self.exposureLockedAtMs.map { .number($0) } ?? .null,
                        "ae_unlock_at_ms": self.exposureUnlockedAtMs.map { .number($0) } ?? .null,
                        "ae_awb_restored": .bool(self.autoRestored),
                        "first_pts_seconds": self.videoWriter.snapshot.firstPTSSeconds.map { .number($0) } ?? .null,
                        "first_receipt_host_seconds": self.firstReceiptHostSeconds.map { .number($0) } ?? .null
                    ]
                    continuation.resume(returning: (self.frontalTask, self.hostFrameTimes, self.regions,
                        self.duplicates.ratio, self.aeAwbLocked, self.frontalAtMs, self.firstHostSeconds, self.clockDeltaMs, diagnostic))
                }
            }
        guard let job = partial.0, let jpeg = await job.value, !jpeg.isEmpty,
              let frontal = partial.5, let first = partial.6, let delta = partial.7 else { throw FaceTimelineError.missingEvidence }
        return FaceEvidence(jpeg: jpeg, frameTimes: partial.1, regionMeans: partial.2,
            duplicateRatio: partial.3, aeAwbLocked: partial.4, frontalAtMs: frontal,
            firstHostSeconds: first, clockDeltaMs: delta, diagnostics: partial.8)
    }

    nonisolated private func clearEvidence() {
        frontalTask?.cancel(); frontalTask = nil
        recordingID = nil
        timeline = nil; firstHostSeconds = nil; clockDeltaMs = nil; frontalAtMs = nil
        hostFrameTimes = []; regions = []; duplicates = DuplicateFrameMeter()
        baselineDone = false; colorsDone = false; aeAwbLocked = false; captureComplete = false
        exposureLockedAtMs = nil; exposureUnlockedAtMs = nil; firstReceiptHostSeconds = nil; autoRestored = false
    }

    nonisolated private func lockExposure() {
        baselineDone = true
        guard let device else { return }
        do {
            try device.lockForConfiguration()
            defer { device.unlockForConfiguration() }
            if device.isExposureModeSupported(.locked) { device.exposureMode = .locked }
            if device.isWhiteBalanceModeSupported(.locked) { device.whiteBalanceMode = .locked }
            aeAwbLocked = device.exposureMode == .locked && device.whiteBalanceMode == .locked
        } catch { aeAwbLocked = false }
    }

    nonisolated private func restoreAutoExposure() {
        autoRestored = false
        guard let device else { return }
        do {
            try device.lockForConfiguration()
            defer { device.unlockForConfiguration() }
            if device.isExposureModeSupported(.continuousAutoExposure) { device.exposureMode = .continuousAutoExposure }
            if device.isWhiteBalanceModeSupported(.continuousAutoWhiteBalance) { device.whiteBalanceMode = .continuousAutoWhiteBalance }
            autoRestored = device.exposureMode == .continuousAutoExposure && device.whiteBalanceMode == .continuousAutoWhiteBalance
        } catch { /* Report lock outcome separately; never invent successful locking. */ }
    }

    nonisolated func discardRecording() {
        queue.async {
            self.videoWriter.cancel(preserveCompleted: false)
            self.restoreAutoExposure()
            self.clearEvidence()
        }
    }

    nonisolated func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer,
                                   from connection: AVCaptureConnection) {
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        latestFormat = CMSampleBufferGetFormatDescription(sampleBuffer)
        // EVERY delivered frame reaches the writer, before the every-other-frame Vision gate.
        let previousFrames = videoWriter.snapshot.frames
        if !captureComplete {
            videoWriter.append(sampleBuffer, mirrored: connection.isVideoMirrored,
                portrait: connection.videoOrientation == .portrait)
        }
        // PTS here is only for diagnostics, NOT the future AVAssetWriter t0.
        let pts = CMSampleBufferGetPresentationTimeStamp(sampleBuffer).seconds
        let accepted = videoWriter.snapshot.frames > previousFrames
        if accepted {
            // Convert the session clock to host time rather than assuming identical epochs.
            guard let sourceClock = session.synchronizationClock else {
                videoWriter.cancel(preserveCompleted: false); restoreAutoExposure(); return
            }
            let host = CMSyncConvertTime(CMSampleBufferGetPresentationTimeStamp(sampleBuffer),
                                        from: sourceClock, to: CMClockGetHostTimeClock()).seconds
            guard host.isFinite else { videoWriter.cancel(preserveCompleted: false); restoreAutoExposure(); return }
            if firstHostSeconds == nil {
                firstHostSeconds = host; clockDeltaMs = (host - pts) * 1000
                firstReceiptHostSeconds = CACurrentMediaTime()
            }
            hostFrameTimes.append(FrameTime(captureTime: host * 1000, presentedFrames: videoWriter.snapshot.frames,
                                            mediaTime: videoWriter.snapshot.elapsed))
        }
        if accepted, let timeline {
            let elapsed = videoWriter.snapshot.elapsed * 1000
            if duplicates.pairs < 30, let thumb = DuplicateFrameMeter.thumbnail(pixelBuffer) { duplicates.add(thumb) }
            if frontalTask == nil, elapsed >= Double(timeline.frontalAtMs),
               elapsed < Double(timeline.baselineMs), let owned = FrontalPixels.copy(pixelBuffer) {
                frontalAtMs = elapsed
                frontalTask = Task.detached(priority: .userInitiated) { owned.jpeg() }
            }
            if !timeline.passive, !baselineDone, elapsed >= Double(timeline.baselineMs) {
                lockExposure(); exposureLockedAtMs = elapsed
            }
            if !timeline.passive, !colorsDone, elapsed >= Double(timeline.colorsEndMs) {
                colorsDone = true; restoreAutoExposure()
                exposureUnlockedAtMs = elapsed
            }
            if elapsed >= Double(timeline.endMs) { captureComplete = true }
        }
        if videoWriter.snapshot.phase == .failed { restoreAutoExposure() }
        let publishMeter = meter.record(pts: pts, width: CVPixelBufferGetWidth(pixelBuffer), height: CVPixelBufferGetHeight(pixelBuffer))
        let analyzeFrame = meter.frames % 2 == 1
        guard analyzeFrame || publishMeter else { return }
        if analyzeFrame {
            let result = tracker.analyze(pixelBuffer, timestamp: pts)
            tracking = result
            quality = gate.update(result.signal, trackerFailed: result.errorCode != nil)
            if accepted, timeline != nil, let signal = result.signal, signal.faces == 1, let box = signal.box,
               let captureTime = hostFrameTimes.last?.captureTime,
               let measured = Regions.measure(pixelBuffer, box: box, hostMs: captureTime), regions.count < 1801 {
                regions.append(measured)
            }
        }
        observer?(FrontCameraSnapshot(runID: runID, configurations: configurationCount,
            inputs: session.inputs.count, outputs: session.outputs.count, meter: meter,
            mirrored: connection.isVideoMirrored, portrait: connection.videoOrientation == .portrait,
            tracking: tracking, quality: quality, recording: videoWriter.snapshot,
            firstHostSeconds: firstHostSeconds, clockDeltaMs: clockDeltaMs, recordingID: recordingID))
    }

    nonisolated func captureOutput(_ output: AVCaptureOutput, didDrop sampleBuffer: CMSampleBuffer,
                                   from connection: AVCaptureConnection) {
        meter.dropped()
    }
}

@MainActor
final class FrontCameraSession: ObservableObject {
    private let worker: FrontCameraWorker
    let previewLayer: AVCaptureVideoPreviewLayer
    let pipelineID = UUID().uuidString
    @Published private(set) var starting = false
    @Published private(set) var running = false
    @Published private(set) var receivingFrames = false
    @Published private(set) var failure: FrontCameraError?
    @Published private(set) var snapshot: FrontCameraSnapshot?
    @Published private(set) var recording = false
    @Published private(set) var finishing = false
    @Published private(set) var recordedVideo: RecordedVideo?
    @Published private(set) var inspection: VideoInspection?
    @Published private(set) var recordingError: VideoWriterError?
    private(set) var recordingAttemptID: UUID?
    private var generation = 0
    private var stopping = false
    private var firstFrameDeadline: Task<Void, Never>?
    private var staleFrameWatchdog: Task<Void, Never>?
    private var lastFrameReceipt: TimeInterval?
    private var lastReceivedFrame = 0

    // All three instances live as long as this face-capture controller, not a phase view.
    init() {
        let worker = FrontCameraWorker()
        self.worker = worker
        previewLayer = AVCaptureVideoPreviewLayer(session: worker.session)
        previewLayer.videoGravity = .resizeAspectFill
    }

    var sessionID: String { String(describing: ObjectIdentifier(worker.session)) }
    var outputID: String { String(describing: ObjectIdentifier(worker.output)) }
    var previewID: String { String(describing: ObjectIdentifier(previewLayer)) }

    func start() async {
        guard !starting, !running else { return }
        generation += 1
        let current = generation
        starting = true
        failure = nil
        receivingFrames = false
        snapshot = nil
        lastFrameReceipt = nil
        lastReceivedFrame = 0
        defer { if current == generation { starting = false } }
        guard await CameraSession.requestPermission() else {
            if current == generation { failure = .denied }
            return
        }
        guard current == generation, !Task.isCancelled else { return }
        do {
            try await worker.start(runID: current) { [weak self] snapshot in
                Task { @MainActor [weak self] in self?.receive(snapshot) }
            }
            guard current == generation else { return }
            guard !Task.isCancelled else { stop(); return }
            running = true
            configurePreview()
            staleFrameWatchdog = Task { [weak self] in
                while !Task.isCancelled {
                    try? await Task.sleep(nanoseconds: 200_000_000)
                    guard !Task.isCancelled, let self, self.generation == current else { return }
                    if let last = self.lastFrameReceipt,
                       ProcessInfo.processInfo.systemUptime - last > QualityGate.maxSampleGap {
                        self.snapshot = nil
                        self.receivingFrames = false
                    }
                }
            }
            firstFrameDeadline = Task { [weak self] in
                try? await Task.sleep(nanoseconds: 5_000_000_000)
                guard !Task.isCancelled, let self, self.generation == current, !self.receivingFrames else { return }
                self.stop()
                self.failure = .noFrames
            }
        } catch {
            if current == generation {
                worker.stop()
                failure = (error as? FrontCameraError) ?? .unavailable
            }
        }
    }

    private func receive(_ value: FrontCameraSnapshot) {
        guard value.runID == generation, value.meter.frames > lastReceivedFrame else { return }
        if recording || finishing, value.recordingID != recordingAttemptID { return }
        lastReceivedFrame = value.meter.frames
        lastFrameReceipt = ProcessInfo.processInfo.systemUptime
        snapshot = value
        if let error = value.recording.failure, recording {
            recording = false
            recordingError = error
        }
        // Error observers may have stopped this run synchronously. Do not turn
        // receivingFrames back on after their teardown.
        guard value.runID == generation else { return }
        receivingFrames = true
        firstFrameDeadline?.cancel()
    }

    func stop() {
        // @Published notifies synchronously in willSet. An observer may call
        // stop() again before the original setter returns (including for flags).
        guard !stopping else { return }
        stopping = true
        defer { stopping = false }
        let wasActive = recording || finishing
        generation += 1
        recording = false
        finishing = false
        firstFrameDeadline?.cancel()
        firstFrameDeadline = nil
        staleFrameWatchdog?.cancel()
        staleFrameWatchdog = nil
        lastFrameReceipt = nil
        starting = false
        running = false
        receivingFrames = false
        snapshot = nil
        worker.stop()
        // Publish only after teardown state is settled. Preserve a more specific
        // writer error instead of replacing it with cancellation.
        if wasActive, recordingError == nil { recordingError = .cancelled }
    }

    func startRecording(timeline: FaceTimeline? = nil, forVoice: Bool = false) async {
        guard running, receivingFrames, (forVoice || snapshot?.quality.ready == true), !recording, !finishing else { return }
        let current = generation
        let attemptID = UUID()
        recordingAttemptID = attemptID
        recording = true
        recordedVideo = nil
        inspection = nil
        recordingError = nil
        do {
            try await worker.startRecording(runID: current, timeline: timeline, forVoice: forVoice, attemptID: attemptID)
            guard current == generation else { return }
        } catch {
            if current == generation {
                recording = false
                recordingError = (error as? VideoWriterError) ?? .cannotStart
            }
        }
    }

    func faceEvidence() async throws -> FaceEvidence { try await worker.evidence() }

    func finishRecording() async {
        guard recording, !finishing else { return }
        let current = generation
        recording = false
        finishing = true
        defer { if current == generation { finishing = false } }
        do {
            let video = try await worker.finishRecording()
            let inspection = try await VideoInspection.inspect(video)
            guard current == generation, !Task.isCancelled else { return }
            self.inspection = inspection
            recordedVideo = video // Only a completed, inspected MP4 can reach export/upload.
        } catch {
            if current == generation {
                worker.discardRecording()
                recordedVideo = nil
                inspection = nil
                recordingError = (error as? VideoWriterError) ?? .invalidOutput
            }
        }
    }

    func discardRecording() {
        guard !recording, !finishing else { return }
        recordedVideo = nil
        inspection = nil
        recordingError = nil
        worker.discardRecording()
    }

    func configurePreview() {
        guard let connection = previewLayer.connection else { return }
        if connection.isVideoOrientationSupported { connection.videoOrientation = .portrait }
        if connection.isVideoMirroringSupported {
            connection.automaticallyAdjustsVideoMirroring = false
            connection.isVideoMirrored = true
        }
    }
}

private final class FrontCameraPreviewHost: UIView {
    var camera: FrontCameraSession?
    let faceLayer = CAShapeLayer()

    override func layoutSubviews() {
        super.layoutSubviews()
        guard let camera else { return }
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        defer { CATransaction.commit() }
        camera.previewLayer.frame = bounds
        camera.configurePreview()
        faceLayer.frame = bounds
        if let snapshot = camera.snapshot, let box = snapshot.tracking?.signal?.box,
           let rect = FacePreviewGeometry.rect(box: box,
               image: CGSize(width: snapshot.meter.width, height: snapshot.meter.height),
               view: bounds.size, mirrored: camera.previewLayer.connection?.isVideoMirrored == true) {
            faceLayer.path = UIBezierPath(rect: rect).cgPath
            faceLayer.strokeColor = snapshot.quality.ready ? UIColor.systemGreen.cgColor : UIColor.systemYellow.cgColor
        } else { faceLayer.path = nil }
    }
}

struct FrontCameraPreview: UIViewRepresentable {
    let camera: FrontCameraSession

    func makeUIView(context: Context) -> UIView {
        let host = FrontCameraPreviewHost()
        host.backgroundColor = .black
        host.camera = camera
        // Reattach the SAME layer if SwiftUI recreates its hosting UIView.
        camera.previewLayer.removeFromSuperlayer()
        host.layer.addSublayer(camera.previewLayer)
        host.faceLayer.fillColor = UIColor.clear.cgColor
        host.faceLayer.lineWidth = 2
        host.layer.addSublayer(host.faceLayer)
        host.clipsToBounds = true
        return host
    }

    func updateUIView(_ uiView: UIView, context: Context) { uiView.setNeedsLayout() }

    static func dismantleUIView(_ uiView: UIView, coordinator: ()) {
        guard let host = uiView as? FrontCameraPreviewHost else { return }
        // Do not detach a layer already adopted by a replacement host.
        if host.camera?.previewLayer.superlayer === host.layer { host.camera?.previewLayer.removeFromSuperlayer() }
        host.camera = nil
    }
}
