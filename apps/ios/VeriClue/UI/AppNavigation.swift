import AVFoundation
import Combine
import SwiftUI

@MainActor
final class AppNavigation: ObservableObject {
    @Published var path: [Route] = []

    var current: Route { path.last ?? .bankStart }

    func go(_ route: Route) {
        guard current != route else { return }
        path.append(route)
    }

    func replaceTop(with route: Route) {
        if !path.isEmpty { path.removeLast() }
        if route != .bankStart { path.append(route) }
    }

    func back() {
        guard !path.isEmpty else { return }
        path.removeLast()
    }

    func toBank() {
        path.removeAll()
    }

    func returnTo(_ route: Route) {
        if let index = path.lastIndex(of: route) {
            path.removeSubrange(path.index(after: index)..<path.endIndex)
        } else { go(route) }
    }
}

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
                if voice ? self.voice.stage == .completed : self.face.stage == .completed { return }
                if FlowRules.sessionExpired(session.expiresAt) {
                    self.restartFace(live: live)
                    self.expiryDestination = .errorSession
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

struct AppNavigationView: View {
    @StateObject private var navigation = AppNavigation()
    @StateObject private var flow = DemoFlow()
    @StateObject private var identity = IdentityFlow()
    @StateObject private var captures = CaptureFlows()
    @Environment(\.scenePhase) private var scenePhase
    private var face: FaceCaptureFlow { captures.face }
    private var voice: VoiceCaptureFlow { captures.voice }
    private var liveMode: Bool { flow.useLiveAPI && !flow.previewMode }

    private var navigationPath: Binding<[Route]> {
        // Read during body evaluation, not only inside NavigationStack's getter.
        // The stack must receive the path snapshot from this render when go()
        // publishes a change; the setter still intercepts native Back gestures.
        let renderedPath = navigation.path
        return Binding(get: { renderedPath }, set: { next in
            if liveMode, next.count < navigation.path.count {
                if [.errorSession, .success, .review, .bankOpened, .deny, .recoveryRequired].contains(navigation.current) {
                    finishAtBank(); return
                }
                if FlowRules.confirmsCaptureExit(navigation.current) {
                    captures.showExitConfirmation = true
                    return
                }
                identity.cancelPendingRequests()
                if next.isEmpty { finishAtBank(); return }
            }
            navigation.path = next
        })
    }

    var body: some View {
        NavigationStack(path: navigationPath) {
            BankStartScreen(
                onOpenAccount: {
                    flow.previewMode = false
                    captures.leaveFlow(live: identity.liveFlow)
                    identity.reset()
                    navigation.go(.splash)
                },
                onGallery: { navigation.go(.gallery) }
            )
            .navigationDestination(for: Route.self) { route in
                RouteScreen(route: route)
                    .environmentObject(navigation)
                    .environmentObject(flow)
                    .environmentObject(identity)
                    .environmentObject(face)
                    .environmentObject(voice)
                    .environmentObject(captures)
            }
        }
        .environmentObject(navigation)
        .environmentObject(flow)
        .environmentObject(identity)
        .environmentObject(face)
        .environmentObject(voice)
        .environmentObject(captures)
        .confirmationDialog("Bạn muốn dừng xác minh?", isPresented: $captures.showExitConfirmation, titleVisibility: .visible) {
            Button("Quay lại chuẩn bị") {
                captures.restartFace(live: identity.liveFlow)
                navigation.returnTo(.faceReady)
            }
            Button("Dừng xác minh", role: .destructive, action: finishAtBank)
            Button("Tiếp tục", role: .cancel) {}
        }
        .onChange(of: scenePhase) { phase in
            guard liveMode else { return }
            if phase == .background { captures.background(at: navigation.current) }
            else if phase == .active { captures.validatePermissions(at: navigation.current) }
        }
        .onChange(of: captures.expiryDestination) { route in
            if liveMode, let route { navigation.replaceTop(with: route) }
        }
    }

    private func finishAtBank() {
        captures.leaveFlow(live: identity.liveFlow)
        identity.reset(); flow.resetForBank(); navigation.toBank()
    }
}
