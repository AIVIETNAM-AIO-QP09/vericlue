import SwiftUI

struct VcLogo: View {
    @Environment(\.vcColors) private var colors

    var body: some View {
        HStack(spacing: 7) {
            VCMark().fill(colors.primary).frame(width: 30, height: 20).accessibilityHidden(true)
            Text("VeriClue")
                .font(VcType.section)
                .foregroundStyle(colors.ink)
        }
        .accessibilityElement(children: .combine)
    }
}

struct VcTopBar: View {
    let onBack: (() -> Void)?
    var title: String? = nil

    @Environment(\.vcColors) private var colors

    var body: some View {
        HStack(spacing: 8) {
            if let onBack {
                Button(action: onBack) {
                    Image(systemName: "arrow.left")
                        .frame(width: 44, height: 44)
                }
                .accessibilityLabel("Quay lại")
            }
            if let title {
                Text(title).font(VcType.section)
            } else {
                VcLogo()
            }
            Spacer()
        }
        .foregroundStyle(colors.ink)
        .frame(height: 56)
        .padding(.horizontal, 8)
    }
}

struct VcStepProgress: View {
    let step: Int
    let total: Int
    @Environment(\.vcColors) private var colors
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.vcReduceMotionOverride) private var previewReduceMotion
    @Environment(\.vcCameraLayout) private var cameraLayout

    init(step: Int, total: Int = 3) {
        self.step = step
        self.total = total
    }

    private var label: String {
        switch step {
        case 1: "Danh tính"
        case 2: "Khuôn mặt"
        default: "Giọng nói"
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                ForEach(1...total, id: \.self) { index in
                    Capsule()
                        .fill(index == total && index <= step ? colors.warmAccent : index <= step ? colors.accent : colors.border)
                        .frame(height: 4)
                        .animation(reduceMotion || previewReduceMotion || cameraLayout ? nil : .easeInOut(duration: 0.25), value: step)
                }
            }
            (Text("Bước \(step)/\(total) · ").foregroundColor(colors.muted)
                + Text(label).foregroundColor(colors.ink))
                .font(VcType.footnote)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
    }
}

struct VcScreen<Content: View>: View {
    var step: Int? = nil
    var centered = false
    var showsLogo = true
    @ViewBuilder let content: Content

    @Environment(\.vcColors) private var colors

    init(step: Int? = nil, centered: Bool = false, showsLogo: Bool = true, @ViewBuilder content: () -> Content) {
        self.step = step
        self.centered = centered
        self.showsLogo = showsLogo
        self.content = content()
    }

    var body: some View {
        GeometryReader { geometry in
                ScrollView {
                    VStack(alignment: centered ? .center : .leading, spacing: 24) { content }
                        .padding(.horizontal, 20)
                        .padding(.vertical, 24)
                        .frame(maxWidth: .infinity, minHeight: centered ? geometry.size.height : 0,
                               alignment: centered ? .center : .topLeading)
                }
        }
        .safeAreaInset(edge: .top, spacing: 0) {
            if let step { VcStepProgress(step: step).background(colors.background) }
        }
        .background(colors.background.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if showsLogo {
                ToolbarItem(placement: .principal) { VcLogo() }
            }
        }
    }
}

struct VcTitleBlock: View {
    let title: String
    var bodyText: String? = nil
    var eyebrow: String? = nil
    var centered = false
    @Environment(\.vcColors) private var colors

    var body: some View {
        VStack(alignment: centered ? .center : .leading, spacing: 8) {
            if let eyebrow {
                Text(eyebrow).font(VcType.labelExtraSmall).foregroundStyle(colors.accent)
            }
            Text(title)
                .font(VcType.titleLarge)
                .tracking(-0.5)
                .fixedSize(horizontal: false, vertical: true)
                .foregroundStyle(colors.ink)
                .multilineTextAlignment(centered ? .center : .leading)
                .frame(maxWidth: .infinity, alignment: centered ? .center : .leading)
            if let bodyText {
                Text(bodyText)
                    .font(VcType.body)
                    .foregroundStyle(colors.muted)
                    .multilineTextAlignment(centered ? .center : .leading)
            }
        }
        .frame(maxWidth: .infinity, alignment: centered ? .center : .leading)
    }
}

struct VcPrimaryButton: View {
    let title: String
    let action: () -> Void
    var enabled = true
    @Environment(\.vcColors) private var colors
    @Environment(\.vcCameraLayout) private var cameraLayout
    @Environment(\.isEnabled) private var isEnabled

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(cameraLayout ? VcType.cameraButton : VcType.button)
                .foregroundStyle(enabled && isEnabled ? colors.onPrimary : colors.onDisabled)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.horizontal, 20).padding(.vertical, 12)
                .frame(maxWidth: .infinity, minHeight: cameraLayout ? 52 : 56)
                .contentShape(Rectangle())
        }
            .buttonStyle(VcPressStyle(filled: true, enabled: enabled))
            .disabled(!enabled)
    }
}

struct VcSecondaryButton: View {
    let title: String
    let action: () -> Void
    @Environment(\.vcColors) private var colors
    @Environment(\.isEnabled) private var isEnabled

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(VcType.button)
                .foregroundStyle(isEnabled ? colors.accent : colors.onDisabled)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.horizontal, 16).padding(.vertical, 12)
                .frame(maxWidth: .infinity, minHeight: 52)
                // Include transparent padding and gaps between wrapped lines in hit testing.
                .contentShape(Rectangle())
        }
            .buttonStyle(VcPressStyle(filled: false))
    }
}

private struct VcPressStyle: ButtonStyle {
    let filled: Bool
    var enabled = true
    @Environment(\.vcColors) private var colors
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.vcReduceMotionOverride) private var previewReduceMotion
    @Environment(\.vcCameraLayout) private var cameraLayout
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .background(filled ? (enabled && isEnabled ? (configuration.isPressed ? colors.primaryPressed : colors.primary) : colors.disabled) : Color.clear,
                        in: Capsule())
            .contentShape(Capsule())
            .scaleEffect(VcMotion.pressScale(pressed: configuration.isPressed && enabled && isEnabled,
                                           reduceMotion: reduceMotion || previewReduceMotion, cameraLayout: cameraLayout))
            // Both pressed endpoints preserve contrast with the same label tone.
            .animation(reduceMotion || previewReduceMotion || cameraLayout ? nil : .easeOut(duration: 0.11), value: configuration.isPressed)
    }
}

enum VcTone { case info, warning, success }

struct VcBanner: View {
    let text: String
    var tone: VcTone = .info
    var systemImage: String? = nil
    @Environment(\.vcColors) private var colors
    @Environment(\.vcCameraLayout) private var cameraLayout

    private var palette: (Color, Color, Color) {
        switch tone {
        case .info: (colors.surfaceSubtle, colors.border, colors.muted)
        case .warning: (colors.warnBackground, colors.warnBorder, colors.warn)
        case .success: (colors.okBackground, colors.okBackground, colors.ok)
        }
    }

    var body: some View {
        let (background, border, foreground) = palette
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: systemImage ?? defaultIcon)
                .font(.system(size: 17, weight: .medium))
            Text(text).font(cameraLayout ? VcType.caption : VcType.body)
                .fixedSize(horizontal: false, vertical: true)
        }
        .foregroundStyle(foreground)
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.vertical, cameraLayout ? 12 : 8).padding(.horizontal, cameraLayout ? 12 : 0)
        .background(cameraLayout ? background : Color.clear, in: RoundedRectangle(cornerRadius: 12))
        .overlay { if cameraLayout { RoundedRectangle(cornerRadius: 12).stroke(border) } }
    }

    private var defaultIcon: String {
        switch tone {
        case .info: "info.circle"
        case .warning: "exclamationmark.triangle"
        case .success: "checkmark.circle"
        }
    }
}

struct VcInfoRow: View {
    let systemImage: String
    let title: String
    var detail: String? = nil
    @Environment(\.vcColors) private var colors

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: systemImage)
                .frame(width: 22)
                .foregroundStyle(colors.accent)
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(detail == nil ? VcType.bodySmall : VcType.label)
                if let detail { Text(detail).font(VcType.caption).foregroundStyle(colors.muted) }
            }
        }
        .foregroundStyle(colors.ink)
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(colors.surfaceSubtle, in: RoundedRectangle(cornerRadius: 12))
    }
}

struct VcStatusBadge: View {
    let systemImage: String
    var tone: VcTone = .info
    var spinning = false
    @Environment(\.vcColors) private var colors

    var body: some View {
        ZStack {
            Circle().fill(background).frame(width: 96, height: 96)
            if spinning {
                ProgressView().tint(foreground).scaleEffect(1.4)
            } else {
                Image(systemName: systemImage)
                    .font(.system(size: 42, weight: .medium))
                    .foregroundStyle(foreground)
            }
        }
        .accessibilityHidden(true)
    }

    private var background: Color {
        switch tone {
        case .success: colors.okBackground
        case .warning: colors.warnBackground
        case .info: colors.surfaceInfo
        }
    }

    private var foreground: Color {
        switch tone {
        case .success: colors.ok
        case .warning: colors.warn
        case .info: colors.accent
        }
    }
}

enum VcRowState { case done, doing, waiting }

struct VcChecklistRow: Identifiable {
    let id = UUID()
    let systemImage: String?
    let label: String
    var state: VcRowState? = nil
    var trailing: String? = nil
}

struct VcChecklistCard: View {
    var title: String? = nil
    let rows: [VcChecklistRow]
    @Environment(\.vcColors) private var colors
    @Environment(\.dynamicTypeSize) private var typeSize

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if let title { Text(title).font(VcType.labelSmall).foregroundStyle(colors.muted) }
            ForEach(Array(rows.enumerated()), id: \.element.id) { index, row in
                HStack(alignment: .top, spacing: 12) {
                    if row.state != nil || row.systemImage != nil { stateIcon(row).frame(width: 24, height: 24) }
                    if typeSize.isAccessibilitySize {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(row.label).font(VcType.bodyStrong).foregroundStyle(colors.ink)
                            trailing(row)
                        }
                    } else {
                        Text(row.label).font(VcType.bodyStrong).foregroundStyle(colors.ink)
                        Spacer(minLength: 8)
                        trailing(row)
                    }
                }
                .fixedSize(horizontal: false, vertical: true)
                if index < rows.count - 1 { Rectangle().fill(colors.border).frame(height: 1).accessibilityHidden(true) }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(colors.surface, in: RoundedRectangle(cornerRadius: 16))
    }

    @ViewBuilder private func trailing(_ row: VcChecklistRow) -> some View {
        if let value = row.trailing ?? stateLabel(row.state), !value.isEmpty {
            Text(value).font(VcType.caption).foregroundStyle(row.state == .done ? colors.ok : colors.muted)
                .multilineTextAlignment(typeSize.isAccessibilitySize ? .leading : .trailing)
        }
    }

    @ViewBuilder private func stateIcon(_ row: VcChecklistRow) -> some View {
        if let state = row.state {
            switch state {
            case .done:
                Image(systemName: "checkmark.circle.fill").foregroundStyle(colors.ok)
            case .doing:
                ProgressView().tint(colors.accent)
            case .waiting:
                Circle().stroke(colors.border, lineWidth: 2).frame(width: 20, height: 20)
            }
        } else if let systemImage = row.systemImage {
            Image(systemName: systemImage).foregroundStyle(colors.accent)
        }
    }

    private func stateLabel(_ state: VcRowState?) -> String? {
        switch state {
        case .done: "Xong"
        case .doing: "Đang xử lý"
        case .waiting: "Chờ"
        case nil: nil
        }
    }
}

struct VcNumericKeypad: View {
    let onDigit: (Character) -> Void
    let onBackspace: () -> Void
    let onDone: () -> Void
    @Environment(\.vcColors) private var colors
    @Environment(\.dynamicTypeSize) private var typeSize

    private let letters: [Character: String] = [
        "2": "ABC", "3": "DEF", "4": "GHI", "5": "JKL", "6": "MNO",
        "7": "PQRS", "8": "TUV", "9": "WXYZ", "0": "+"
    ]

    var body: some View {
        VStack(spacing: 6) {
            ForEach(["123", "456", "789"], id: \.self) { row in
                HStack(spacing: 6) {
                    ForEach(Array(row), id: \.self) { digit in
                        key(background: colors.key) { onDigit(digit) } label: { digitLabel(digit) }
                            .accessibilityLabel(String(digit))
                            .accessibilityIdentifier("keypad-digit-\(digit)")
                    }
                }
            }
            HStack(spacing: 6) {
                key(background: colors.border, action: onBackspace) {
                    Image(systemName: "delete.backward").foregroundStyle(colors.ink)
                }
                .accessibilityLabel("Xóa một số")
                .accessibilityIdentifier("keypad-delete")
                key(background: colors.key) { onDigit("0") } label: { digitLabel("0") }
                    .accessibilityLabel("0")
                    .accessibilityIdentifier("keypad-digit-0")
                key(background: colors.primary, action: onDone) {
                    Image(systemName: "checkmark").foregroundStyle(colors.onPrimary)
                }
                .accessibilityLabel("Xác nhận trên bàn phím")
                .accessibilityIdentifier("keypad-done")
            }
        }
        .padding(6)
        .background(colors.keypad)
    }

    private func key<Label: View>(background: Color, action: @escaping () -> Void, @ViewBuilder label: () -> Label) -> some View {
        Button(action: action) {
            label().frame(maxWidth: .infinity, minHeight: 50).contentShape(Rectangle())
        }
            .buttonStyle(.plain)
            .background(background, in: RoundedRectangle(cornerRadius: 8))
    }

    private func digitLabel(_ digit: Character) -> some View {
        VStack(spacing: 0) {
            Text(String(digit)).font(Font.custom(VcFont.medium.rawValue, size: 22, relativeTo: .title2))
            // Letter hints are redundant for numeric OTP/phone input. At accessibility
            // sizes omit them rather than shrinking the digit or consuming the viewport.
            if !typeSize.isAccessibilitySize, let letters = letters[digit] {
                Text(letters).font(VcType.footnote).scaleEffect(0.75)
            }
        }
        .foregroundStyle(colors.ink)
    }
}

struct VcOTPBoxes: View {
    let code: String
    let hasError: Bool
    @Environment(\.vcColors) private var colors

    var body: some View {
        HStack(spacing: 8) {
            ForEach(0..<6, id: \.self) { index in
                let character = Array(code).indices.contains(index) ? String(Array(code)[index]) : nil
                let active = index == code.count
                Text(character ?? "–")
                    .font(VcType.titleMedium)
                    .foregroundStyle(character == nil ? colors.muted : colors.ink)
                    .frame(maxWidth: .infinity, minHeight: 56)
                    .background(hasError ? colors.warnBackground : colors.surface, in: RoundedRectangle(cornerRadius: 10))
                    .overlay(
                        RoundedRectangle(cornerRadius: 10)
                            .stroke(hasError ? colors.warnBorder : (character != nil || active ? colors.accent : colors.border), lineWidth: active && !hasError ? 2 : 1)
                    )
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Mã xác nhận \(code.count) trên 6 số")
        .accessibilityIdentifier("otp-code")
        .accessibilityValue(code)
    }
}

struct VcLoadingPresentation: View {
    let title: String
    let bodyText: String

    var body: some View {
        VcScreen(centered: true) {
            VcStatusBadge(systemImage: "arrow.triangle.2.circlepath", spinning: true)
            VcTitleBlock(title: title, bodyText: bodyText, centered: true)
        }
    }
}
