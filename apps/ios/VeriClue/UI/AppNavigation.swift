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
}

struct AppNavigationView: View {
    @StateObject private var navigation = AppNavigation()
    @StateObject private var flow = DemoFlow()

    var body: some View {
        NavigationStack(path: $navigation.path) {
            BankStartScreen(
                onOpenAccount: {
                    flow.previewMode = false
                    navigation.go(.splash)
                },
                onGallery: { navigation.go(.gallery) }
            )
            .navigationDestination(for: Route.self) { route in
                RouteScreen(route: route)
                    .environmentObject(navigation)
                    .environmentObject(flow)
            }
        }
        .environmentObject(navigation)
        .environmentObject(flow)
    }
}
