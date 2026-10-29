import Foundation
import SwiftUI
import Testing
import UIKit
@testable import VeriClue

@MainActor
struct WarmThemeTests {
    private func rgb(_ color: Color) -> UInt32 {
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        UIColor(color).getRed(&r, green: &g, blue: &b, alpha: &a)
        return UInt32((r * 255).rounded()) << 16 | UInt32((g * 255).rounded()) << 8 | UInt32((b * 255).rounded())
    }

    private func contrast(_ first: Color, _ second: Color) -> Double {
        func luminance(_ color: Color) -> Double {
            let value = rgb(color)
            func channel(_ shift: UInt32) -> Double {
                let v = Double((value >> shift) & 255) / 255
                return v <= 0.04045 ? v / 12.92 : pow((v + 0.055) / 1.055, 2.4)
            }
            return 0.2126 * channel(16) + 0.7152 * channel(8) + 0.0722 * channel(0)
        }
        let a = luminance(first), b = luminance(second)
        return (max(a, b) + 0.05) / (min(a, b) + 0.05)
    }

    @Test func lightTokensMatchAndroidWarmMinimalPalette() {
        let c = VcColors.light
        #expect(rgb(c.background) == 0xFAF8F5 && rgb(c.surface) == 0xFFFFFF)
        #expect(rgb(c.primary) == 0x0C2345 && rgb(c.primaryPressed) == 0x07172F)
        #expect(rgb(c.ink) == 0x14202B && rgb(c.muted) == 0x5B6670)
        #expect(rgb(c.border) == 0xECE7E0 && rgb(c.warmAccent) == 0xE8743B)
        #expect(rgb(c.ok) == 0x176940 && rgb(c.success) == 0x1E8A5A)
    }

    @Test func darkTokensAreIndependentAndNotWhiteOnLightButtons() {
        let c = VcColors.dark
        #expect(rgb(c.background) == 0x0E1822 && rgb(c.surface) == 0x192A3A)
        #expect(rgb(c.primary) == 0xB5C9E3 && rgb(c.onPrimary) == 0x14202B)
        #expect(rgb(c.primaryPressed) == 0xCFDDF0 && rgb(c.surfaceSubtle) == 0x1C2F42)
    }

    @Test(arguments: [false, true])
    func textContrastIncludesPressedDisabledAndSemanticStates(_ dark: Bool) {
        let c = dark ? VcColors.dark : .light
        for background in [c.background, c.surface, c.surfaceSubtle] {
            #expect(contrast(c.ink, background) >= 4.5)
            #expect(contrast(c.muted, background) >= 4.5)
        }
        #expect(contrast(c.onPrimary, c.primary) >= 4.5)
        #expect(contrast(c.onPrimary, c.primaryPressed) >= 4.5)
        #expect(contrast(c.onDisabled, c.disabled) >= 4.5)
        #expect(contrast(c.ok, c.okBackground) >= 4.5)
        #expect(contrast(c.warn, c.warnBackground) >= 4.5)
        #expect(contrast(VcPalette.ink, c.warmAccent) >= 4.5)
    }

    @Test func reduceMotionAndCameraDisableOnlyDecorativeTransforms() {
        #expect(VcMotion.pressScale(pressed: true, reduceMotion: false, cameraLayout: false) == 0.97)
        #expect(VcMotion.pressScale(pressed: true, reduceMotion: true, cameraLayout: false) == 1)
        #expect(VcMotion.pressScale(pressed: true, reduceMotion: false, cameraLayout: true) == 1)
        #expect(VcMotion.pressScale(pressed: false, reduceMotion: false, cameraLayout: false) == 1)
    }

    @Test func allFourBundledFontsExistAndNoBrandTextUsesSystemGlyphs() {
        #expect(VcFont.allCases.count == 4 && VcFont.missingPostScriptNames.isEmpty)
        for face in VcFont.allCases { #expect(UIFont(name: face.rawValue, size: 32)?.fontName == face.rawValue) }
        #expect(!VCMark().path(in: CGRect(x: 0, y: 0, width: 150, height: 100)).isEmpty)
    }

    @Test func challengeFlashPaletteHasNotBeenRestyled() {
        #expect(rgb(VcPalette.flashGrey) == 0xD1D1D1)
        #expect(rgb(VcPalette.flashBlue) == 0xCFE9FF)
        #expect(rgb(VcPalette.flashPink) == 0xFFD6EF)
        #expect(rgb(VcPalette.flashYellow) == 0xFFEFC2)
        #expect(rgb(VcPalette.flashMint) == 0xCFF2DC)
    }

    #if DEBUG
    @Test func screenshotOverridesAreOptInAndPresentationOnly() {
        let defaults = ThemePreviewConfiguration(arguments: [])
        #expect(defaults.colorScheme == nil && defaults.typeSize == nil && !defaults.reduceMotion)
        let preview = ThemePreviewConfiguration(arguments: ["--vc-theme", "dark", "--vc-text-size", "accessibility3", "--vc-reduce-motion"])
        #expect(preview.colorScheme == .dark && preview.typeSize == .accessibility3 && preview.reduceMotion)
    }
    #endif
}
