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

    init() {
        let face = FaceCaptureFlow()
        self.face = face
        voice = VoiceCaptureFlow(camera: face.camera)
    }
}

struct AppNavigationView: View {
    @StateObject private var navigation = AppNavigation()
    @StateObject private var flow = DemoFlow()
    @StateObject private var identity = IdentityFlow()
    @StateObject private var captures = CaptureFlows()
    private var face: FaceCaptureFlow { captures.face }
    private var voice: VoiceCaptureFlow { captures.voice }

    var body: some View {
        NavigationStack(path: $navigation.path) {
            BankStartScreen(
                onOpenAccount: {
                    flow.previewMode = false
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
            }
        }
        .environmentObject(navigation)
        .environmentObject(flow)
        .environmentObject(identity)
        .environmentObject(face)
        .environmentObject(voice)
    }
}
