import SwiftUI

struct VcLogo: View {
    @Environment(\.vcColors) private var colors

    var body: some View {
        HStack(spacing: 7) {
            Image(systemName: "checkmark.shield.fill")
                .foregroundStyle(colors.accent)
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
                        .fill(index <= step ? colors.accent : colors.border)
                        .frame(height: 4)
                        .animation(.easeInOut(duration: 0.5), value: step)
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
        Group {
            if centered {
                VStack(spacing: 24) {
                    Spacer(minLength: 16)
                    content
                    Spacer(minLength: 16)
                }
                .padding(.horizontal, 20)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 24) { content }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 20)
                        .padding(.vertical, 24)
                }
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

    var body: some View {
        Button(title, action: action)
            .font(VcType.button)
            .foregroundStyle(enabled ? Color.white : colors.onDisabled)
            .frame(maxWidth: .infinity, minHeight: 52)
            .background(enabled ? colors.primary : colors.disabled, in: RoundedRectangle(cornerRadius: 12))
            .disabled(!enabled)
    }
}

struct VcSecondaryButton: View {
    let title: String
    let action: () -> Void
    @Environment(\.vcColors) private var colors

    var body: some View {
        Button(title, action: action)
            .font(VcType.button)
            .foregroundStyle(colors.accent)
            .frame(maxWidth: .infinity, minHeight: 52)
            .background(colors.isDark ? Color.clear : colors.surfaceInfo, in: RoundedRectangle(cornerRadius: 12))
            .overlay(RoundedRectangle(cornerRadius: 12).stroke(colors.border))
    }
}

enum VcTone { case info, warning, success }

struct VcBanner: View {
    let text: String
    var tone: VcTone = .info
    var systemImage: String? = nil
    @Environment(\.vcColors) private var colors

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
            Text(text).font(VcType.caption)
        }
        .foregroundStyle(foreground)
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(background, in: RoundedRectangle(cornerRadius: 12))
        .overlay(RoundedRectangle(cornerRadius: 12).stroke(border))
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

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if let title { Text(title).font(VcType.labelSmall).foregroundStyle(colors.muted) }
            ForEach(rows) { row in
                HStack(spacing: 12) {
                    stateIcon(row)
                        .frame(width: 24, height: 24)
                    Text(row.label).font(VcType.bodyStrong).foregroundStyle(colors.ink)
                    Spacer()
                    if let trailing = row.trailing ?? stateLabel(row.state) {
                        Text(trailing).font(VcType.caption).foregroundStyle(row.state == .done ? colors.ok : colors.muted)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(18)
        .background(colors.surfaceSubtle, in: RoundedRectangle(cornerRadius: 16))
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
                    }
                }
            }
            HStack(spacing: 6) {
                key(background: colors.border, action: onBackspace) {
                    Image(systemName: "delete.backward").foregroundStyle(colors.ink)
                }
                key(background: colors.key) { onDigit("0") } label: { digitLabel("0") }
                key(background: colors.primary, action: onDone) {
                    Image(systemName: "checkmark").foregroundStyle(.white)
                }
            }
        }
        .padding(6)
        .background(colors.keypad)
    }

    private func key<Label: View>(background: Color, action: @escaping () -> Void, @ViewBuilder label: () -> Label) -> some View {
        Button(action: action) { label().frame(maxWidth: .infinity, minHeight: 50) }
            .buttonStyle(.plain)
            .background(background, in: RoundedRectangle(cornerRadius: 8))
    }

    private func digitLabel(_ digit: Character) -> some View {
        VStack(spacing: 0) {
            Text(String(digit)).font(Font.custom(VcFont.medium.rawValue, size: 22, relativeTo: .title2))
            if let letters = letters[digit] {
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
