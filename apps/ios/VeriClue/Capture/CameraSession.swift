import AVFoundation
import Combine
import CoreImage
import Foundation
import QuartzCore
import SwiftUI
import UIKit

enum CameraError: Error { case denied, unavailable, emptyPhoto, cancelled, captureFailed }

// AVCaptureSession configuration, start/stop and photo continuations belong to this queue.
// UI only attaches the session to a preview layer; it does not mutate its inputs/outputs.
private final class RearCameraWorker: NSObject, AVCapturePhotoCaptureDelegate, AVCaptureVideoDataOutputSampleBufferDelegate, @unchecked Sendable {
    nonisolated(unsafe) let session = AVCaptureSession()
    nonisolated private let queue = DispatchQueue(label: "vn.vericlue.id-camera", qos: .userInitiated)
    nonisolated(unsafe) private let output = AVCapturePhotoOutput()
    nonisolated(unsafe) private let videoOutput = AVCaptureVideoDataOutput()
    nonisolated private let analysisQueue = DispatchQueue(label: "vn.vericlue.id-card-analysis", qos: .userInitiated)
    nonisolated private let imageContext = CIContext()
    // Only touched on analysisQueue. No frames/text/QR are logged or retained.
    nonisolated(unsafe) private var onSample: (@Sendable (IDCardObservation) -> Void)?
    nonisolated(unsafe) private var lastSampleAt = 0.0
    nonisolated(unsafe) private var configured = false
    nonisolated(unsafe) private var pending: CheckedContinuation<Data, Error>?
    nonisolated(unsafe) private var photoId: Int64?

    nonisolated func start(onSample: @escaping @Sendable (IDCardObservation) -> Void) async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            queue.async {
                do {
                    if !self.configured {
                        guard let device = AVCaptureDevice.default(.builtInWideAngleCamera, for: .video, position: .back) else {
                            throw CameraError.unavailable
                        }
                        let input = try AVCaptureDeviceInput(device: device)
                        self.session.beginConfiguration()
                        defer { self.session.commitConfiguration() }
                        self.session.sessionPreset = .photo
                        guard self.session.canAddInput(input), self.session.canAddOutput(self.output) else {
                            throw CameraError.unavailable
                        }
                        self.session.addInput(input)
                        self.session.addOutput(self.output)
                        // Unsupported sampling must not remove the manual shutter fallback.
                        if self.session.canAddOutput(self.videoOutput) {
                            self.videoOutput.alwaysDiscardsLateVideoFrames = true
                            self.videoOutput.videoSettings = [kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA]
                            self.videoOutput.setSampleBufferDelegate(self, queue: self.analysisQueue)
                            self.session.addOutput(self.videoOutput)
                            if let connection = self.videoOutput.connection(with: .video), connection.isVideoOrientationSupported {
                                connection.videoOrientation = .portrait
                                if connection.isVideoMirroringSupported {
                                    connection.automaticallyAdjustsVideoMirroring = false
                                    connection.isVideoMirrored = false
                                }
                            }
                        }
                        self.configured = true
                    }
                    self.analysisQueue.async { self.lastSampleAt = 0; self.onSample = onSample }
                    if !self.session.isRunning { self.session.startRunning() }
                    guard self.session.isRunning else { throw CameraError.unavailable }
                    continuation.resume()
                } catch { continuation.resume(throwing: CameraError.unavailable) }
            }
        }
    }

    nonisolated func stop() {
        queue.async {
            self.analysisQueue.async { self.onSample = nil }
            if self.session.isRunning { self.session.stopRunning() }
            self.finish(id: self.photoId, result: .failure(CameraError.cancelled))
        }
    }

    nonisolated func captureOutput(_ output: AVCaptureOutput, didOutput sampleBuffer: CMSampleBuffer,
                                   from connection: AVCaptureConnection) {
        let now = CACurrentMediaTime()
        guard let onSample, now - lastSampleAt >= 0.5 else { return }
        lastSampleAt = now
        autoreleasepool {
            guard let buffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
            let raw = CIImage(cvPixelBuffer: buffer)
            let scale = min(1, 1600 / max(raw.extent.width, raw.extent.height))
            let image = raw.transformed(by: CGAffineTransform(scaleX: scale, y: scale))
            guard let cgImage = imageContext.createCGImage(image, from: image.extent) else { return }
            do { onSample(try IDCardAnalyzer.observe(cgImage)) }
            catch { onSample(IDCardObservation(sharpness: 0, glareFraction: 1,
                looksLikeCard: false, hasQR: false, sampledAt: now)) }
        }
    }

    nonisolated func capture() async throws -> Data {
        try await withCheckedThrowingContinuation { continuation in
            queue.async {
                guard self.session.isRunning, self.pending == nil else {
                    continuation.resume(throwing: CameraError.unavailable)
                    return
                }
                let settings = AVCapturePhotoSettings(format: [AVVideoCodecKey: AVVideoCodecType.jpeg])
                settings.flashMode = .off
                self.pending = continuation
                self.photoId = settings.uniqueID
                if let connection = self.output.connection(with: .video), connection.isVideoOrientationSupported {
                    connection.videoOrientation = .portrait
                    if connection.isVideoMirroringSupported {
                        connection.automaticallyAdjustsVideoMirroring = false
                        connection.isVideoMirrored = false
                    }
                }
                let id = settings.uniqueID
                self.output.capturePhoto(with: settings, delegate: self)
                self.queue.asyncAfter(deadline: .now() + 12) {
                    self.finish(id: id, result: .failure(CameraError.captureFailed))
                }
            }
        }
    }

    nonisolated func photoOutput(_ output: AVCapturePhotoOutput, didFinishProcessingPhoto photo: AVCapturePhoto, error: Error?) {
        let id = photo.resolvedSettings.uniqueID
        let data = error == nil ? photo.fileDataRepresentation() : nil
        queue.async {
            if let data, !data.isEmpty { self.finish(id: id, result: .success(data)) }
            else { self.finish(id: id, result: .failure(CameraError.emptyPhoto)) }
        }
    }

    nonisolated func photoOutput(_ output: AVCapturePhotoOutput, didFinishCaptureFor resolvedSettings: AVCaptureResolvedPhotoSettings, error: Error?) {
        guard error != nil else { return }
        let id = resolvedSettings.uniqueID
        queue.async { self.finish(id: id, result: .failure(CameraError.captureFailed)) }
    }

    nonisolated private func finish(id: Int64?, result: Result<Data, Error>) {
        guard id == photoId, let continuation = pending else { return }
        pending = nil
        photoId = nil
        continuation.resume(with: result)
    }
}

@MainActor
final class CameraSession: ObservableObject {
    private let worker = RearCameraWorker()
    @Published private(set) var ready = false
    @Published private(set) var busy = false
    @Published private(set) var failure: CameraError?
    @Published private(set) var observation: IDCardObservation?
    @Published private(set) var shouldAutoCapture = false
    private var auto = IDAutoCapture()
    private var isBack = false
    private var generation = 0
    var session: AVCaptureSession { worker.session }

    static func requestPermission() async -> Bool {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: true
        case .notDetermined: await AVCaptureDevice.requestAccess(for: .video)
        default: false
        }
    }

    func start(isBack: Bool = false) async {
        guard !ready, !busy else { return }
        let current = generation
        busy = true
        defer { if current == generation { busy = false } }
        failure = nil
        self.isBack = isBack
        observation = nil; shouldAutoCapture = false
        guard await Self.requestPermission() else {
            if current == generation { failure = .denied }
            return
        }
        guard current == generation, !Task.isCancelled else { return }
        do {
            try await worker.start { [weak self] sample in
                guard let owner = self else { return }
                Task { @MainActor in owner.receive(sample, generation: current) }
            }
            guard current == generation else { return }
            guard !Task.isCancelled else { worker.stop(); return }
            ready = true
            auto.begin(at: CACurrentMediaTime())
        } catch { if current == generation { failure = .unavailable } }
    }

    func stop() {
        generation += 1
        ready = false
        busy = false
        auto.cancel(); shouldAutoCapture = false; observation = nil
        worker.stop()
    }

    func capture() async throws -> IDCardPhoto {
        guard ready, !busy, auto.claim() else { throw CameraError.unavailable }
        let current = generation
        busy = true
        defer { if current == generation { busy = false } }
        do {
            let bytes = try await worker.capture()
            let photo = try await Task.detached(priority: .userInitiated) { try IDCardAnalyzer.analyze(bytes) }.value
            guard current == generation, !Task.isCancelled else { throw CameraError.cancelled }
            return photo
        } catch {
            if current == generation { auto.begin(at: CACurrentMediaTime()); shouldAutoCapture = false }
            throw error
        }
    }

    private func receive(_ sample: IDCardObservation, generation id: Int) {
        guard id == generation, ready, !busy else { return }
        observation = sample
        shouldAutoCapture = auto.offer(good: sample.good(isBack: isBack), at: sample.sampledAt)
    }
}

private final class CameraPreviewView: UIView {
    override class var layerClass: AnyClass { AVCaptureVideoPreviewLayer.self }
    var previewLayer: AVCaptureVideoPreviewLayer { layer as! AVCaptureVideoPreviewLayer }
}

struct RearCameraPreview: UIViewRepresentable {
    let session: AVCaptureSession

    func makeUIView(context: Context) -> UIView {
        let view = CameraPreviewView()
        view.backgroundColor = .black
        view.previewLayer.session = session
        view.previewLayer.videoGravity = .resizeAspectFill
        return view
    }
    func updateUIView(_ uiView: UIView, context: Context) {
        guard let view = uiView as? CameraPreviewView else { return }
        if let connection = view.previewLayer.connection, connection.isVideoOrientationSupported {
            connection.videoOrientation = .portrait
            if connection.isVideoMirroringSupported {
                connection.automaticallyAdjustsVideoMirroring = false
                connection.isVideoMirrored = false
            }
        }
    }
    static func dismantleUIView(_ uiView: UIView, coordinator: ()) {
        (uiView as? CameraPreviewView)?.previewLayer.session = nil
    }
}
