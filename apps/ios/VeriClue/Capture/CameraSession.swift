import AVFoundation
import Combine
import Foundation
import SwiftUI
import UIKit

enum CameraError: Error { case denied, unavailable, emptyPhoto, cancelled, captureFailed }

// AVCaptureSession configuration, start/stop and photo continuations belong to this queue.
// UI only attaches the session to a preview layer; it does not mutate its inputs/outputs.
private final class RearCameraWorker: NSObject, AVCapturePhotoCaptureDelegate, @unchecked Sendable {
    nonisolated(unsafe) let session = AVCaptureSession()
    nonisolated private let queue = DispatchQueue(label: "vn.vericlue.id-camera", qos: .userInitiated)
    nonisolated(unsafe) private let output = AVCapturePhotoOutput()
    nonisolated(unsafe) private var configured = false
    nonisolated(unsafe) private var pending: CheckedContinuation<Data, Error>?
    nonisolated(unsafe) private var photoId: Int64?

    nonisolated func start() async throws {
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
                        self.configured = true
                    }
                    if !self.session.isRunning { self.session.startRunning() }
                    guard self.session.isRunning else { throw CameraError.unavailable }
                    continuation.resume()
                } catch { continuation.resume(throwing: CameraError.unavailable) }
            }
        }
    }

    nonisolated func stop() {
        queue.async {
            if self.session.isRunning { self.session.stopRunning() }
            self.finish(id: self.photoId, result: .failure(CameraError.cancelled))
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
                    if connection.isVideoMirroringSupported { connection.isVideoMirrored = false }
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
    private var generation = 0
    var session: AVCaptureSession { worker.session }

    static func requestPermission() async -> Bool {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: true
        case .notDetermined: await AVCaptureDevice.requestAccess(for: .video)
        default: false
        }
    }

    func start() async {
        guard !ready, !busy else { return }
        let current = generation
        busy = true
        defer { if current == generation { busy = false } }
        failure = nil
        guard await Self.requestPermission() else {
            if current == generation { failure = .denied }
            return
        }
        guard current == generation, !Task.isCancelled else { return }
        do {
            try await worker.start()
            guard current == generation else { return }
            guard !Task.isCancelled else { worker.stop(); return }
            ready = true
        } catch { if current == generation { failure = .unavailable } }
    }

    func stop() {
        generation += 1
        ready = false
        busy = false
        worker.stop()
    }

    func capture() async throws -> IDCardPhoto {
        guard ready, !busy else { throw CameraError.unavailable }
        let current = generation
        busy = true
        defer { if current == generation { busy = false } }
        let bytes = try await worker.capture()
        let photo = try await Task.detached(priority: .userInitiated) { try IDCardAnalyzer.analyze(bytes) }.value
        guard current == generation, !Task.isCancelled else { throw CameraError.cancelled }
        return photo
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
            if connection.isVideoMirroringSupported { connection.isVideoMirrored = false }
        }
    }
    static func dismantleUIView(_ uiView: UIView, coordinator: ()) {
        (uiView as? CameraPreviewView)?.previewLayer.session = nil
    }
}
