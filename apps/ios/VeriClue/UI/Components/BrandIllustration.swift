import SwiftUI

// Native path port of this repository's Android drawable/logo_mark.xml (150 x 100).
// No bitmap, external asset or font glyph is used for the mark.
struct VCMark: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: 3, y: 13)); p.addLine(to: CGPoint(x: 25, y: 13))
        p.addCurve(to: CGPoint(x: 45, y: 27), control1: CGPoint(x: 35, y: 13), control2: CGPoint(x: 40, y: 18))
        p.addLine(to: CGPoint(x: 62, y: 57)); p.addLine(to: CGPoint(x: 82, y: 24))
        p.addCurve(to: CGPoint(x: 129, y: 5), control1: CGPoint(x: 93, y: 6), control2: CGPoint(x: 111, y: 0))
        p.addCurve(to: CGPoint(x: 146, y: 18), control1: CGPoint(x: 137, y: 7), control2: CGPoint(x: 143, y: 12))
        p.addCurve(to: CGPoint(x: 104, y: 32), control1: CGPoint(x: 130, y: 10), control2: CGPoint(x: 115, y: 16))
        p.addLine(to: CGPoint(x: 74, y: 81))
        p.addCurve(to: CGPoint(x: 42, y: 80), control1: CGPoint(x: 66, y: 94), control2: CGPoint(x: 50, y: 93))
        p.closeSubpath()
        p.move(to: CGPoint(x: 146, y: 32))
        p.addCurve(to: CGPoint(x: 106, y: 3), control1: CGPoint(x: 141, y: 13), control2: CGPoint(x: 125, y: 3))
        p.addCurve(to: CGPoint(x: 58, y: 34), control1: CGPoint(x: 85, y: 3), control2: CGPoint(x: 70, y: 15))
        p.addLine(to: CGPoint(x: 49, y: 48)); p.addLine(to: CGPoint(x: 67, y: 75))
        p.addCurve(to: CGPoint(x: 114, y: 96), control1: CGPoint(x: 77, y: 92), control2: CGPoint(x: 95, y: 99))
        p.addCurve(to: CGPoint(x: 146, y: 73), control1: CGPoint(x: 130, y: 94), control2: CGPoint(x: 142, y: 84))
        p.addCurve(to: CGPoint(x: 107, y: 72), control1: CGPoint(x: 131, y: 80), control2: CGPoint(x: 117, y: 79))
        p.addCurve(to: CGPoint(x: 87, y: 48), control1: CGPoint(x: 97, y: 66), control2: CGPoint(x: 91, y: 57))
        p.addCurve(to: CGPoint(x: 121, y: 30), control1: CGPoint(x: 95, y: 33), control2: CGPoint(x: 107, y: 27))
        p.closeSubpath()
        let scale = min(rect.width / 150, rect.height / 100)
        return p.applying(CGAffineTransform(scaleX: scale, y: scale)
            .concatenating(CGAffineTransform(translationX: rect.midX - 75 * scale, y: rect.midY - 50 * scale)))
    }
}

struct VCSuccessEmblem: View {
    @Environment(\.vcColors) private var colors
    var checked = true
    var body: some View {
        ZStack(alignment: .bottomTrailing) {
            Circle().fill(VcPalette.logoNavy)
            VCMark().fill(.white).padding(26)
            if checked {
                Image(systemName: "checkmark").font(.system(size: 16, weight: .bold))
                    .foregroundStyle(colors.isDark ? VcPalette.darkBackground : .white)
                    .frame(width: 32, height: 32).background(colors.success, in: Circle())
                    .overlay(Circle().stroke(colors.background, lineWidth: 4))
            }
        }
        .frame(width: 116, height: 116)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Biểu trưng VeriClue")
        .accessibilityIdentifier("vc-brand-emblem")
    }
}

struct VCWelcomeIllustration: View {
    @Environment(\.vcColors) private var colors
    var body: some View {
        GeometryReader { geometry in
            ZStack {
                Circle().stroke(colors.warmAccent, style: StrokeStyle(lineWidth: 1.5, dash: [5, 6]))
                    .frame(width: 158, height: 158).offset(x: 70)
                RoundedRectangle(cornerRadius: 14).fill(colors.illustration)
                    .frame(width: 186, height: 118)
                    .overlay {
                        HStack(spacing: 14) {
                            RoundedRectangle(cornerRadius: 8).fill(colors.border).frame(width: 42, height: 54)
                            VStack(alignment: .leading, spacing: 12) {
                                Capsule().fill(colors.muted.opacity(0.35)).frame(width: 78, height: 6)
                                Capsule().fill(colors.muted.opacity(0.25)).frame(width: 64, height: 6)
                                Capsule().fill(colors.warmAccent).frame(width: 32, height: 6)
                            }
                        }
                    }
                    .rotationEffect(.degrees(-9)).offset(x: -56)
                VCSuccessEmblem(checked: false).offset(x: 70)
            }
            .frame(width: 340, height: 172)
            .scaleEffect(min(1, geometry.size.width / 340))
            .position(x: geometry.size.width / 2, y: geometry.size.height / 2)
        }
        .frame(height: 172)
        .accessibilityHidden(true)
    }
}

struct VCSampleAccount: View {
    @Environment(\.vcColors) private var colors
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Dữ liệu mẫu").font(VcType.caption).foregroundStyle(colors.muted)
            Text("0123 4567 8901").font(VcType.account).monospacedDigit()
                .foregroundStyle(colors.ink).fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading).padding(20)
        .background(colors.surface, in: RoundedRectangle(cornerRadius: 16))
    }
}

struct VCNumberedRow: View {
    let number: Int
    let title: String
    var detail: String? = nil
    @Environment(\.vcColors) private var colors
    @ScaledMetric(relativeTo: .caption) private var badgeDiameter: CGFloat = 32
    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            Text(String(number)).font(VcType.label).foregroundStyle(number == 3 ? VcPalette.ink : .white)
                .frame(width: badgeDiameter, height: badgeDiameter)
                .background(number == 3 ? colors.warmAccent : VcPalette.logoNavy, in: Circle())
            VStack(alignment: .leading, spacing: 4) {
                Text(title).font(VcType.bodyStrong).foregroundStyle(colors.ink)
                if let detail { Text(detail).font(VcType.caption).foregroundStyle(colors.muted) }
            }
            .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(.vertical, 8)
    }
}
