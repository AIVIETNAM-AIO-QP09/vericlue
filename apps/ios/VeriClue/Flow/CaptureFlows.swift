import AVFoundation
import Combine
import Foundation

@MainActor
final class CaptureFlows: ObservableObject {
    let face: FaceCaptureFlow
    let voice: VoiceCaptureFlow
    let startupCleanupCount: Int
    @Published var showExitConfirmation = false
    @Published private(set) var expiryDestination: Route?
    private var expiryMonitor: Task<Void, Never>?

    init() {
        startupCleanupCount = CaptureFileStore.cleanupOrphans() // Before any recorder exists.
        let face = FaceCaptureFlow()
        self.face = face
        voice = VoiceCaptureFlow(camera: face.camera)
    }

    func restartFace(live: LiveFlow?) {
        voice.cancel(); face.cancel(); live?.abandonFaceAttempt()
    }

    func confirmIdentity(_ identity: IdentityFlow) async -> Route? {
        guard let pendingID = face.pendingCaptureID else { return .faceExpired }
        if let route = face.validatePendingCapture() { return route }
        let route = await identity.confirmCard()
        guard face.pendingCaptureID == pendingID else { return nil }
        if let invalid = face.validatePendingCapture() { return invalid }
        if let route, route != .uploading { face.cancel() }
        return route
    }

    func leaveFlow(live: LiveFlow?) {
        expiryMonitor?.cancel(); expiryMonitor = nil; expiryDestination = nil
        restartFace(live: live)
        live?.reset()
    }

    func monitorExpiry(live: LiveFlow?, voice: Bool = false) {
        expiryMonitor?.cancel()
        expiryDestination = nil
        guard let live else { return }
        expiryMonitor = Task { [weak self, weak live] in
            while !Task.isCancelled {
                guard let self, let live, let session = live.session else { return }
                if live.hasVerifiedPass { return } // Receipt metadata cannot turn a pass into expiry.
                if voice ? self.voice.stage == .completed : self.face.stage == .completed { return }
                if FlowRules.sessionExpired(session.expiresAt) {
                    self.restartFace(live: live)
                    self.expiryDestination = .errorSession
                    return
                }
                if !voice, self.face.hasPendingCapture, self.face.stage != .uploading,
                   let route = self.face.validatePendingCapture() {
                    self.expiryDestination = route
                    return
                }
                try? await Task.sleep(for: .milliseconds(500))
            }
        }
    }

    func background(at route: Route) {
        if [.voice, .voiceAgain].contains(route) {
            if voice.stage == .uploading { face.camera.stop() }
            else { voice.interrupt() }
        } else if [.faceReady, .framing, .holdStill, .turnHead].contains(route) {
            if face.stage == .uploading { face.camera.stop() }
            else { face.interrupt() }
        }
    }

    func validatePermissions(at route: Route) {
        guard FlowRules.confirmsCaptureExit(route) else { return }
        let camera = AVCaptureDevice.authorizationStatus(for: .video)
        let microphone = AVCaptureDevice.authorizationStatus(for: .audio)
        if [.voice, .voiceAgain].contains(route) {
            guard voice.stage != .uploading, !voice.retryUpload else { return }
            if camera == .denied || camera == .restricted { voice.interrupt(route: .errorCamera) }
            else if microphone == .denied || microphone == .restricted { voice.interrupt(route: .errorMic) }
        } else if camera == .denied || camera == .restricted {
            face.interrupt(route: .errorCamera)
        }
    }
}
