import SwiftUI

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
        // The live-flow adapter intercepts native Back for capture ownership.
        // Read its path during body evaluation so pushes publish into the stack.
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
        // Demo/Gallery needs no exit interception: use SwiftUI's projected binding
        // so native pushes/pops are not reconciled through a captured path snapshot.
        NavigationStack(path: liveMode ? navigationPath : $navigation.path) {
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
                identity.cancelPendingRequests()
                captures.restartFace(live: identity.liveFlow)
                navigation.restartFace()
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
            if liveMode, let route {
                identity.cancelPendingRequests()
                navigation.replaceTop(with: route)
            }
        }
    }

    private func finishAtBank() {
        captures.leaveFlow(live: identity.liveFlow)
        identity.reset(); flow.resetForBank(); navigation.toBank()
    }
}
