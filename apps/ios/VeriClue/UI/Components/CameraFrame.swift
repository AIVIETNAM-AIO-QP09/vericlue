import SwiftUI

struct VcCameraFrame: View {
    var cardMode = false
    var glare = false
    var guidance: String? = nil
    var progress: Double? = nil
    @Environment(\.vcColors) private var colors

    var body: some View {
        GeometryReader { geometry in
            ZStack {
                LinearGradient(
                    colors: [Color(hex: 0x2A3038), VcPalette.cameraBackground],
                    startPoint: .top,
                    endPoint: .bottom
                )
                if cardMode { cardPlaceholder }
                else { facePlaceholder(in: geometry.size) }
                if glare { Color.white.opacity(0.35) }
                frameOverlay
                if let guidance {
                    Text(guidance)
                        .font(VcType.label)
                        .foregroundStyle(VcPalette.ink)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                        .background(.white, in: Capsule())
                        .padding(.bottom, 24)
                        .frame(maxHeight: .infinity, alignment: .bottom)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 18))
        }
        .aspectRatio(cardMode ? 1.586 : 0.74, contentMode: .fit)
        .accessibilityLabel(cardMode ? "Khung chụp căn cước" : "Khung khuôn mặt")
    }

    private var cardPlaceholder: some View {
        RoundedRectangle(cornerRadius: 16)
            .fill(Color(hex: 0xDDEDEA))
            .overlay(alignment: .leading) {
                VStack(alignment: .leading, spacing: 12) {
                    Capsule().fill(Color(hex: 0x9DB7B2)).frame(width: 120, height: 9)
                    Capsule().fill(Color(hex: 0x9DB7B2)).frame(width: 170, height: 9)
                    Capsule().fill(Color(hex: 0x9DB7B2)).frame(width: 100, height: 9)
                }
                .padding(24)
            }
            .padding(28)
    }

    private func facePlaceholder(in size: CGSize) -> some View {
        VStack(spacing: 0) {
            Ellipse()
                .fill(Color(hex: 0x6B5A50))
                .frame(width: size.width * 0.40, height: size.width * 0.52)
            Ellipse()
                .fill(Color(hex: 0x1C2733))
                .frame(width: size.width * 0.70, height: size.width * 0.40)
                .offset(y: -8)
        }
    }

    @ViewBuilder private var frameOverlay: some View {
        if cardMode {
            RoundedRectangle(cornerRadius: 18)
                .stroke(colors.accent, lineWidth: 3)
                .padding(24)
        } else {
            ZStack {
                Ellipse()
                    .stroke(.white.opacity(0.9), lineWidth: 2)
                    .padding(.horizontal, 54)
                    .padding(.vertical, 42)
                if let progress {
                    Circle()
                        .trim(from: 0, to: max(0, min(progress, 1)))
                        .stroke(colors.ok, style: StrokeStyle(lineWidth: 4, lineCap: .round))
                        .rotationEffect(.degrees(-90))
                        .padding(34)
                }
            }
        }
    }
}
