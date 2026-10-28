import SwiftUI
import UIKit

enum VcPalette {
    static let primary = Color(hex: 0x0C2345)
    static let primaryPressed = Color(hex: 0x07172F)
    static let background = Color(hex: 0xFAF8F5)
    static let ink = Color(hex: 0x14202B)
    static let muted = Color(hex: 0x5B6670)
    static let white = Color.white
    static let surfaceSubtle = Color(hex: 0xF5F1EB)
    static let surfaceInfo = Color(hex: 0xF3E7DC)
    static let border = Color(hex: 0xECE7E0)
    static let warmAccent = Color(hex: 0xE8743B)
    static let darkPrimary = Color(hex: 0xB5C9E3)
    static let darkPressed = Color(hex: 0xCFDDF0)
    static let logoNavy = Color(hex: 0x0C2345)
    static let logoBlue = Color(hex: 0x246BDF)
    static let logoLight = Color(hex: 0x6FA3FF)
    static let darkBackground = Color(hex: 0x0E1822)
    static let darkSurface = Color(hex: 0x192A3A)
    static let darkSubtle = Color(hex: 0x1C2F42)
    static let darkInfo = Color(hex: 0x193954)
    static let darkBorder = Color(hex: 0x344A60)
    static let darkMuted = Color(hex: 0xB7C7D6)
    static let darkAccent = Color(hex: 0x8CC8FF)
    static let ok = Color(hex: 0x176940)
    static let success = Color(hex: 0x1E8A5A)
    static let okBackground = Color(hex: 0xE4F2EA)
    static let okOnDark = Color(hex: 0x4CD497)
    static let warn = Color(hex: 0x8A5A00)
    static let warnBackground = Color(hex: 0xFFF3D6)
    static let warnBorder = Color(hex: 0xE5B84B)
    static let cameraBackground = Color(hex: 0x0D1620)
    static let bankGreen = Color(hex: 0x0F6E56)
    static let flashGrey = Color(hex: 0xD1D1D1)
    static let flashBlue = Color(hex: 0xCFE9FF)
    static let flashPink = Color(hex: 0xFFD6EF)
    static let flashYellow = Color(hex: 0xFFEFC2)
    static let flashMint = Color(hex: 0xCFF2DC)
}

struct VcColors {
    let isDark: Bool
    let background: Color
    let surface: Color
    let surfaceSubtle: Color
    let surfaceInfo: Color
    let border: Color
    let ink: Color
    let muted: Color
    let primary: Color
    let primaryPressed: Color
    let onPrimary: Color
    let accent: Color
    let ok: Color
    let okBackground: Color
    let warn: Color
    let warnBackground: Color
    let warnBorder: Color
    let disabled: Color
    let onDisabled: Color
    let keypad: Color
    let key: Color
    let warmAccent: Color
    let illustration: Color
    let success: Color

    static let light = VcColors(
        isDark: false,
        background: VcPalette.background,
        surface: VcPalette.white,
        surfaceSubtle: VcPalette.surfaceSubtle,
        surfaceInfo: VcPalette.surfaceInfo,
        border: VcPalette.border,
        ink: VcPalette.ink,
        muted: VcPalette.muted,
        primary: VcPalette.primary,
        primaryPressed: VcPalette.primaryPressed,
        onPrimary: .white,
        accent: VcPalette.primary,
        ok: VcPalette.ok,
        okBackground: VcPalette.okBackground,
        warn: VcPalette.warn,
        warnBackground: VcPalette.warnBackground,
        warnBorder: VcPalette.warnBorder,
        disabled: VcPalette.border,
        onDisabled: VcPalette.muted,
        keypad: VcPalette.surfaceSubtle,
        key: .white,
        warmAccent: VcPalette.warmAccent,
        illustration: VcPalette.surfaceInfo,
        success: VcPalette.success
    )

    static let dark = VcColors(
        isDark: true,
        background: VcPalette.darkBackground,
        surface: VcPalette.darkSurface,
        surfaceSubtle: VcPalette.darkSubtle,
        surfaceInfo: VcPalette.darkInfo,
        border: VcPalette.darkBorder,
        ink: .white,
        muted: VcPalette.darkMuted,
        primary: VcPalette.darkPrimary,
        primaryPressed: VcPalette.darkPressed,
        onPrimary: VcPalette.ink,
        accent: VcPalette.darkAccent,
        ok: VcPalette.okOnDark,
        okBackground: Color(hex: 0x173A2B),
        warn: Color(hex: 0xFFD27A),
        warnBackground: Color(hex: 0x3A2E12),
        warnBorder: VcPalette.warn,
        disabled: VcPalette.darkBorder,
        onDisabled: VcPalette.darkMuted,
        keypad: Color(hex: 0x16212C),
        key: VcPalette.darkSurface,
        warmAccent: VcPalette.warmAccent,
        illustration: VcPalette.darkInfo,
        success: VcPalette.okOnDark
    )
}

private struct VcColorsKey: EnvironmentKey {
    static let defaultValue = VcColors.light
}

extension EnvironmentValues {
    var vcColors: VcColors {
        get { self[VcColorsKey.self] }
        set { self[VcColorsKey.self] = newValue }
    }
}

enum VcFont: String, CaseIterable {
    case regular = "BeVietnamPro-Regular"
    case medium = "BeVietnamPro-Medium"
    case semibold = "BeVietnamPro-SemiBold"
    case bold = "BeVietnamPro-Bold"

    static var missingPostScriptNames: [String] {
        allCases.compactMap { UIFont(name: $0.rawValue, size: 16) == nil ? $0.rawValue : nil }
    }
}

enum VcType {
    static let titleLarge = Font.custom(VcFont.bold.rawValue, size: 32, relativeTo: .title)
    static let titleMedium = Font.custom(VcFont.bold.rawValue, size: 22, relativeTo: .title2)
    static let section = Font.custom(VcFont.semibold.rawValue, size: 16, relativeTo: .headline)
    static let body = Font.custom(VcFont.regular.rawValue, size: 15, relativeTo: .body)
    static let bodyStrong = Font.custom(VcFont.semibold.rawValue, size: 15, relativeTo: .body)
    static let bodySmall = Font.custom(VcFont.regular.rawValue, size: 14, relativeTo: .subheadline)
    static let caption = Font.custom(VcFont.regular.rawValue, size: 13, relativeTo: .footnote)
    static let footnote = Font.custom(VcFont.regular.rawValue, size: 12, relativeTo: .caption)
    static let button = Font.custom(VcFont.semibold.rawValue, size: 16, relativeTo: .body)
    static let cameraButton = Font.custom(VcFont.semibold.rawValue, size: 15, relativeTo: .body)
    static let account = Font.custom(VcFont.bold.rawValue, size: 26, relativeTo: .title2)
    static let label = Font.custom(VcFont.semibold.rawValue, size: 14, relativeTo: .subheadline)
    static let labelSmall = Font.custom(VcFont.semibold.rawValue, size: 13, relativeTo: .footnote)
    static let labelExtraSmall = Font.custom(VcFont.semibold.rawValue, size: 12, relativeTo: .caption)
}

struct VcThemeRoot<Content: View>: View {
    @Environment(\.colorScheme) private var colorScheme
    private let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        content
            .font(VcType.body)
            .environment(\.vcColors, colorScheme == .dark ? .dark : .light)
            .tint(colorScheme == .dark ? VcPalette.darkAccent : VcPalette.primary)
    }
}

// Presentation policy only; never used by recorders, clocks or the challenge canvas.
enum VcMotion {
    static func pressScale(pressed: Bool, reduceMotion: Bool, cameraLayout: Bool) -> CGFloat {
        pressed && !reduceMotion && !cameraLayout ? 0.97 : 1
    }
}

private struct CameraLayoutKey: EnvironmentKey { static let defaultValue = false }
private struct ReduceMotionOverrideKey: EnvironmentKey { static let defaultValue = false }
extension EnvironmentValues {
    var vcReduceMotionOverride: Bool {
        get { self[ReduceMotionOverrideKey.self] }
        set { self[ReduceMotionOverrideKey.self] = newValue }
    }
    var vcCameraLayout: Bool {
        get { self[CameraLayoutKey.self] }
        set { self[CameraLayoutKey.self] = newValue }
    }
}

extension Color {
    init(hex: UInt32, alpha: Double = 1) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: alpha
        )
    }
}
