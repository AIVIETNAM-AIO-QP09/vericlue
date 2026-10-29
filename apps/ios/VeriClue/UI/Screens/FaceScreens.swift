import SwiftUI

struct FaceReadyScreen: View {
    let onReady: () -> Void
    let onSkipFlash: () -> Void

    var body: some View {
        VcScreen(step: 2) {
            VcTitleBlock(title: "Tiếp theo: quay khuôn mặt", bodyText: "Giữ điện thoại cách mặt khoảng 25 đến 40 cm, ở nơi đủ sáng.")
            VStack(spacing: 10) {
                VcInfoRow(systemImage: "face.smiling", title: "1 · Giữ đầu yên", detail: "Nhìn thẳng. Màn hình sẽ đổi màu nhạt, rồi một chấm sáng chạy: chỉ đưa mắt theo.")
                VcInfoRow(systemImage: "arrow.left.and.right", title: "2 · Quay trái, quay phải", detail: "Làm theo mũi tên.")
            }
            VcBanner(
                text: "Màn hình sẽ đổi màu nhạt trong vài giây. Người nhạy cảm với ánh sáng nhấp nháy không nên tiếp tục. Bạn có thể bấm Dừng bất cứ lúc nào.",
                tone: .warning,
                systemImage: "sun.max.trianglebadge.exclamationmark"
            )
        }
        .safeAreaInset(edge: .bottom) {
            BottomAction {
                VcPrimaryButton(title: "Tôi đã sẵn sàng", action: onReady)
                VcSecondaryButton(title: "Bỏ qua nháy màu, chờ nhân viên xác minh", action: onSkipFlash)
            }
        }
    }
}

struct FramingScreen: View {
    let onCaptured: () -> Void
    @State private var progress = 0.0
    @State private var hint = "Đưa khuôn mặt vào khung"
    @State private var completed = false

    var body: some View {
        ZStack {
            VcPalette.cameraBackground.ignoresSafeArea()
            VStack(spacing: 18) {
                Text("Đưa khuôn mặt vào khung")
                    .font(VcType.titleMedium).foregroundStyle(.white)
                VcCameraFrame(guidance: hint, progress: progress)
                Text(progress >= 1 ? "Đang tự chụp…" : "Ảnh sẽ tự chụp khi đủ điều kiện")
                    .font(VcType.caption).foregroundStyle(.white.opacity(0.75))
                #if DEBUG
                Button("Chụp ngay (debug)", action: finish)
                    .font(VcType.label).foregroundStyle(.white)
                #endif
            }
            .padding(20)
        }
        .toolbarColorScheme(.dark, for: .navigationBar)
        .task {
            let hints = ["Ra chỗ sáng hơn", "Lại gần hơn", "Đưa khuôn mặt vào giữa khung hình", "Tốt, giữ nguyên"]
            for (index, value) in hints.enumerated() {
                guard !Task.isCancelled else { return }
                hint = value
                progress = Double(index + 1) / Double(hints.count)
                try? await Task.sleep(nanoseconds: 550_000_000)
            }
            guard !Task.isCancelled else { return }
            finish()
        }
    }

    private func finish() {
        guard !completed else { return }
        completed = true
        onCaptured()
    }
}

struct FaceTimelineDemoScreen: View {
    let onStop: () -> Void
    let onDone: () -> Void
    @State private var phase = 0
    @State private var background = VcPalette.flashGrey
    @State private var completed = false

    private let colors = [VcPalette.flashGrey, VcPalette.flashBlue, VcPalette.flashPink, VcPalette.flashYellow, VcPalette.flashMint]

    var body: some View {
        ZStack {
            background.ignoresSafeArea()
                .animation(.easeInOut(duration: 0.35), value: background)
            if phase < 5 {
                VStack(spacing: 14) {
                    Image(systemName: "face.smiling").font(.system(size: 70))
                    Text(phase == 0 ? "Giữ yên, nhìn thẳng" : "Giữ yên")
                        .font(VcType.titleMedium)
                    Text("Màn hình sẽ nhấp nháy màu nhạt vài giây. Người nhạy cảm với ánh sáng nhấp nháy không nên tiếp tục.")
                        .font(VcType.caption).multilineTextAlignment(.center)
                }
                .foregroundStyle(VcPalette.ink)
                .padding(30)
            } else {
                FollowDotView()
            }
            VStack {
                Spacer()
                VcSecondaryButton(title: "Dừng", action: stop)
                    .padding(20)
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .task {
            for index in colors.indices {
                guard !Task.isCancelled else { return }
                phase = index
                background = colors[index]
                try? await Task.sleep(nanoseconds: 650_000_000)
            }
            phase = 5
            background = .white
            try? await Task.sleep(nanoseconds: 1_600_000_000)
            guard !Task.isCancelled else { return }
            finish()
        }
    }

    private func stop() {
        guard !completed else { return }
        completed = true
        onStop()
    }

    private func finish() {
        guard !completed else { return }
        completed = true
        onDone()
    }
}

private struct FollowDotView: View {
    @State private var move = false

    var body: some View {
        GeometryReader { geometry in
            ZStack {
                Text("Giữ đầu yên, chỉ đưa mắt theo chấm sáng")
                    .font(VcType.label)
                    .foregroundStyle(VcPalette.ink)
                    .padding(12)
                    .background(.white.opacity(0.85), in: Capsule())
                    .position(x: geometry.size.width / 2, y: 80)
                Circle()
                    .fill(VcPalette.primary.opacity(0.18))
                    .frame(width: 48, height: 48)
                    .overlay(Circle().fill(VcPalette.primary).frame(width: 28, height: 28))
                    .position(
                        x: move ? geometry.size.width - 52 : 52,
                        y: move ? geometry.size.height * 0.68 : geometry.size.height * 0.35
                    )
                    .animation(.linear(duration: 1.4), value: move)
            }
            .onAppear { move = true }
        }
    }
}

struct TurnHeadScreen: View {
    let onDone: () -> Void
    @State private var segment = 0
    @State private var completed = false

    private var title: String {
        switch segment {
        case 0: "Quay sang trái"
        case 1: "Quay sang phải"
        default: "Nhìn thẳng"
        }
    }

    private var icon: String {
        switch segment {
        case 0: "arrow.left"
        case 1: "arrow.right"
        default: "face.smiling"
        }
    }

    var body: some View {
        ZStack {
            VcPalette.cameraBackground.ignoresSafeArea()
            VStack(spacing: 20) {
                Text(title).font(VcType.titleLarge).foregroundStyle(.white)
                VcCameraFrame(progress: Double(segment + 1) / 3)
                Image(systemName: icon)
                    .font(.system(size: 48, weight: .semibold))
                    .foregroundStyle(.white)
                Text("Từ từ, rồi quay lại nhìn thẳng")
                    .font(VcType.body).foregroundStyle(.white.opacity(0.8))
                Text("\(segment + 1) / 3").font(VcType.caption).foregroundStyle(.white.opacity(0.7))
                #if DEBUG
                Button("Bỏ qua (debug)", action: finish).font(VcType.label).foregroundStyle(.white)
                #endif
            }
            .padding(20)
        }
        .toolbarColorScheme(.dark, for: .navigationBar)
        .task {
            for index in 0..<3 {
                guard !Task.isCancelled else { return }
                segment = index
                try? await Task.sleep(nanoseconds: 900_000_000)
            }
            guard !Task.isCancelled else { return }
            finish()
        }
    }

    private func finish() {
        guard !completed else { return }
        completed = true
        onDone()
    }
}
