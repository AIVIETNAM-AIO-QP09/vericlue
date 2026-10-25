//
//  VeriClueTests.swift
//  VeriClueTests
//
//  Created by NÂUQ on 25/10/26.
//

import Foundation
import SwiftUI
import Testing
import UIKit
@testable import VeriClue

@MainActor
struct VeriClueTests {
    @Test func routesMatchIOS01Plan() {
        let expected = Set([
            "bank_start", "bank_opened", "gallery", "splash", "auth", "terms", "consent", "intro", "permission", "phone", "otp", "otp_error",
            "id_front", "id_front_glare", "id_front_review", "id_back", "id_back_review", "confirm", "edit_info", "face_ready", "framing", "hold_still",
            "turn_head", "voice", "voice_again", "uploading", "upload_failed", "checking", "slow", "success", "review", "retry_quality", "retry_challenge",
            "error_camera", "error_mic", "error_network", "error_session", "error_service", "error_device", "interrupted", "no_voice", "exit_confirm", "stopped",
            "flash_skipped", "deny", "recovery_required"
        ])

        #expect(Set(Route.allCases.map(\.rawValue)) == expected)
        #expect(Route.allCases.count == expected.count)
    }

    @Test func navigationDoesNotPushDuplicateTop() {
        let navigation = AppNavigation()
        navigation.go(.auth)
        navigation.go(.auth)
        #expect(navigation.path == [.auth])

        navigation.go(.terms)
        navigation.back()
        #expect(navigation.current == .auth)

        navigation.toBank()
        #expect(navigation.path.isEmpty)
        #expect(navigation.current == .bankStart)
    }

    @Test func threePurposesUseTheExpectedDemoStages() {
        let flow = DemoFlow()

        let onboarding = flow.routeSequence(for: .onboarding)
        #expect(onboarding.contains(.idFront))
        #expect(onboarding.contains(.voice))
        #expect(onboarding.last == .success)

        let reauth = flow.routeSequence(for: .reauth)
        #expect(!reauth.contains(.idFront))
        #expect(!reauth.contains(.voice))
        #expect(reauth.last == .success)

        let recovery = flow.routeSequence(for: .recovery)
        #expect(recovery.contains(.idFront))
        #expect(recovery.contains(.voice))
        #expect(recovery.last == .success)
    }

    @Test func everyDemoOutcomeHasADestination() {
        #expect(DemoOutcome.pass.destination == .success)
        #expect(DemoOutcome.review.destination == .review)
        #expect(DemoOutcome.retryQuality.destination == .retryQuality)
        #expect(DemoOutcome.retryChallenge.destination == .retryChallenge)
        #expect(DemoOutcome.voiceAgain.destination == .voiceAgain)
    }

    @Test func bundledFontsAreRegistered() {
        #expect(VcFont.missingPostScriptNames.isEmpty)
        for font in VcFont.allCases {
            #expect(UIFont(name: font.rawValue, size: 16) != nil)
        }
    }

    @Test func lightAndDarkTextContrastIsReadable() {
        #expect(contrast(VcColors.light.ink, VcColors.light.background) >= 4.5)
        #expect(contrast(VcColors.light.muted, VcColors.light.background) >= 4.5)
        #expect(contrast(VcColors.dark.ink, VcColors.dark.background) >= 4.5)
        #expect(contrast(VcColors.dark.muted, VcColors.dark.background) >= 4.5)
    }

    @Test func userFacingStringLiteralsDoNotContainBannedWords() throws {
        let testsDirectory = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
        let sourceDirectory = testsDirectory.deletingLastPathComponent().appendingPathComponent("VeriClue")
        // apps/ios/docs/plan-ios.md §10. Keep this list at least as strict as the plan.
        let banned = ["giả mạo", "deepfake", "điểm", "score", "ai phát hiện", "gian lận", "độ tin cậy", "%"]
        let regex = try NSRegularExpression(pattern: #"\"(?:[^\"\\]|\\.)*\""#)
        var hits: [String] = []

        let files = FileManager.default.enumerator(at: sourceDirectory, includingPropertiesForKeys: nil)?
            .compactMap { $0 as? URL }
            .filter { $0.pathExtension == "swift" } ?? []

        #expect(!files.isEmpty, "Không tìm thấy source để kiểm tra chữ cấm")

        for file in files {
            let source = try String(contentsOf: file, encoding: .utf8)
            let range = NSRange(source.startIndex..., in: source)
            for match in regex.matches(in: source, range: range) {
                guard let swiftRange = Range(match.range, in: source) else { continue }
                let literal = String(source[swiftRange]).lowercased()
                if banned.contains(where: literal.contains) {
                    hits.append("\(file.lastPathComponent): \(literal)")
                }
            }
        }

        #expect(hits.isEmpty, "Chữ cấm trong nội dung hiển thị: \(hits.joined(separator: ", "))")
    }

    private func contrast(_ foreground: Color, _ background: Color) -> Double {
        let foregroundLuminance = luminance(UIColor(foreground))
        let backgroundLuminance = luminance(UIColor(background))
        let lighter = max(foregroundLuminance, backgroundLuminance)
        let darker = min(foregroundLuminance, backgroundLuminance)
        return (lighter + 0.05) / (darker + 0.05)
    }

    private func luminance(_ color: UIColor) -> Double {
        var red: CGFloat = 0
        var green: CGFloat = 0
        var blue: CGFloat = 0
        var alpha: CGFloat = 0
        color.getRed(&red, green: &green, blue: &blue, alpha: &alpha)

        func channel(_ value: CGFloat) -> Double {
            let component = Double(value)
            return component <= 0.03928 ? component / 12.92 : pow((component + 0.055) / 1.055, 2.4)
        }

        return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)
    }
}
