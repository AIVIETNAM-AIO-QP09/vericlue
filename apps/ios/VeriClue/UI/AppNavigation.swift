import Combine
import Foundation
#if DEBUG
import OSLog
#endif

@MainActor
final class AppNavigation: ObservableObject {
    @Published var path: [Route] = [] {
        didSet {
            #if DEBUG
            if ProcessInfo.processInfo.arguments.contains("--vc-navigation-trace") {
                // Route names only; never include session, OTP, receipt or identity data.
                let routeNames = path.map(\.rawValue).joined(separator: "/")
                Self.trace.notice("path=\(routeNames, privacy: .public)")
            }
            #endif
        }
    }
    #if DEBUG
    private static let trace = Logger(subsystem: "vn.vericlue.app", category: "navigation-qa")
    #endif

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

    func restartFace() {
        // Dispose the previous face/confirm/edit/upload views before installing a new owner.
        if let index = path.firstIndex(where: { [.faceReady, .framing, .holdStill, .turnHead, .confirm, .editInfo].contains($0) }) {
            path.removeSubrange(index..<path.endIndex)
        }
        go(.faceReady)
    }

    func returnTo(_ route: Route) {
        if let index = path.lastIndex(of: route) {
            path.removeSubrange(path.index(after: index)..<path.endIndex)
        } else { go(route) }
    }
}
