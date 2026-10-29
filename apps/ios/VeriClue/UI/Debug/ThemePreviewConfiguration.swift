#if DEBUG
import SwiftUI

struct ThemePreviewConfiguration {
    let colorScheme: ColorScheme?
    let typeSize: DynamicTypeSize?
    let reduceMotion: Bool

    static var current: Self { Self(arguments: ProcessInfo.processInfo.arguments) }

    init(arguments: [String]) {
        func value(_ name: String) -> String? {
            guard let index = arguments.firstIndex(of: name), arguments.indices.contains(index + 1) else { return nil }
            return arguments[index + 1]
        }
        switch value("--vc-theme") {
        case "light": colorScheme = .light
        case "dark": colorScheme = .dark
        default: colorScheme = nil
        }
        typeSize = value("--vc-text-size") == "accessibility3" ? .accessibility3 : nil
        reduceMotion = arguments.contains("--vc-reduce-motion")
    }
}
#endif
