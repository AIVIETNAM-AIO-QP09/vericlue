import Combine
import SwiftUI

struct FaceLiveScreen: View {
    let live: LiveFlow?
    let purpose: Purpose
    let onRoute: (Route) -> Void
    let onClose: () -> Void
    @EnvironmentObject private var face: FaceCaptureFlow
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        ZStack(alignment: .topTrailing) {
            FaceTimelineCanvas(flow: face).ignoresSafeArea()
            VStack(alignment: .leading, spacing: 18) {
                Text(title).font(VcType.titleMedium).padding(.trailing, 110)
                if face.stage == .intro {
                    Text(purpose == .reauth ? "Giữ điện thoại ngang tầm mặt, ở nơi đủ sáng." : "Giữ điện thoại cách mặt khoảng 25 đến 40 cm, ở nơi đủ sáng.")
                        .font(VcType.body).padding(.trailing, 110)
                    if purpose != .reauth {
                        VcBanner(text: "Màn hình sẽ đổi màu nhạt trong vài giây. Người nhạy cảm với ánh sáng nhấp nháy không nên tiếp tục. Bạn có thể bấm Dừng bất cứ lúc nào.", tone: .warning)
                    }
                    VcPrimaryButton(title: "Tôi đã sẵn sàng") { Task { await face.prepare() } }
                }
                if face.stage == .preparing || face.stage == .finishing || face.stage == .uploading { ProgressView() }
                if let error = face.errorText { VcBanner(text: error, tone: .warning) }
                if face.stage == .failed || face.stage == .interrupted {
                    VcPrimaryButton(title: face.retryUpload ? "Thử lại" : "Quay lại chuẩn bị") {
                        Task { if face.retryUpload { await face.submit() } else { await face.prepare() } }
                    }
                }
                if face.stage == .framing { FaceFramingHint(camera: face.camera) }
                if case .head(_, let direction) = face.phase, face.stage == .recording {
                    Image(systemName: direction == "left" ? "arrow.left" : direction == "right" ? "arrow.right" : "face.smiling")
                        .font(.system(size: 56)).frame(maxWidth: .infinity)
                    FaceYawHint(camera: face.camera, direction: direction)
                }
                Spacer()
                #if DEBUG
                if face.lastFrameCount > 0 {
                    Text("Đã thu: \(face.lastFrameCount) frame · \(face.lastEvents.count) màu · \(face.lastRegionCount) mẫu vùng")
                        .font(VcType.caption)
                }
                #endif
                VcSecondaryButton(title: "Dừng xác minh") { face.cancel(); onClose() }
            }
            .padding(20)
            .foregroundStyle(VcPalette.ink)
            // This exact view stays in one position through all four phases.
            FaceSmallPreview(camera: face.camera)
                .frame(width: 96, height: 128)
                .clipShape(RoundedRectangle(cornerRadius: 14))
                .padding(.trailing, 16).padding(.top, 64)
        }
        .environment(\.vcColors, .light)
        .toolbar(.hidden, for: .navigationBar)
        .task { face.configure(live: live, purpose: purpose) }
        .onChange(of: scenePhase) { phase in if phase != .active { face.interrupt() } }
        // Observe changes, not the publisher's initial stored destination when
        // returning from Retry. Replaying it would loop straight back to Retry.
        .onChange(of: face.destination) { route in if let route { onRoute(route) } }
        .onDisappear { face.leaveFaceScreen() }
    }

    private var title: String {
        switch face.stage {
        case .intro: "Tiếp theo: quay khuôn mặt"
        case .preparing: "Đang chuẩn bị"
        case .framing: "Đưa khuôn mặt vào khung"
        case .finishing: "Đang hoàn tất video"
        case .uploading: "Đang gửi dữ liệu"
        case .failed: "Chưa thể tiếp tục"
        case .interrupted: "Xác minh bị gián đoạn"
        default:
            switch face.phase {
            case .baseline: "Giữ yên, nhìn thẳng"
            case .color: "Giữ yên"
            case .gap, .gaze: "Giữ đầu yên, chỉ đưa mắt theo chấm sáng"
            case .head(_, let direction): direction == "left" ? "Quay sang trái" : direction == "right" ? "Quay sang phải" : "Nhìn thẳng"
            case .done: "Đã thu xong phần khuôn mặt"
            }
        }
    }
}

private struct FaceSmallPreview: View {
    @ObservedObject var camera: FrontCameraSession
    var body: some View { FrontCameraPreview(camera: camera) }
}

private struct FaceFramingHint: View {
    @ObservedObject var camera: FrontCameraSession
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(camera.snapshot?.quality.state.guidance ?? "Đưa khuôn mặt vào khung").font(VcType.body)
            ProgressView(value: min(1, Double(camera.snapshot?.quality.heldMs ?? 0) / 1000))
        }
        .padding(.top, 100)
    }
}

private struct FaceYawHint: View {
    @ObservedObject var camera: FrontCameraSession
    let direction: String
    var body: some View {
        if let yaw = camera.snapshot?.tracking?.signal?.yaw {
            let signed = direction == "left" ? -yaw : direction == "right" ? yaw : max(0, 25 - abs(yaw))
            ProgressView(value: min(1, max(0, signed / 25)))
                .accessibilityLabel("Làm theo hướng dẫn và giữ nguyên đến khi đổi bước")
        }
    }
}

struct LiveFaceRetryScreen: View {
    @ObservedObject var live: LiveFlow
    @EnvironmentObject private var face: FaceCaptureFlow
    let onRetry: () -> Void
    let quality: Bool
    var body: some View {
        VcScreen(step: 2) {
            VcTitleBlock(title: quality ? "Chụp lại" : "Làm lại thử thách",
                         bodyText: quality ? FlowRules.retryHintText(live.retryHint) : "Hãy làm lại theo hướng dẫn trên màn hình.")
            if let attempts = live.attemptsLeft { Text("Còn \(attempts) lần chụp lại").font(VcType.body) }
            #if DEBUG
            Text("Lượt vừa gửi: \(face.lastAttemptChallengeId ?? "—")").font(VcType.caption)
            Text("Lượt tiếp theo: \(live.challenge?.challengeId ?? "—")").font(VcType.caption)
            #endif
            VcPrimaryButton(title: "Quay lại chuẩn bị", action: onRetry)
        }
    }
}

// IOS-04 hands off the real server prompt and keeps the same camera controller.
// Never let the IOS-01 demo microphone/auto-success act on a live API session.
struct LiveVoicePendingScreen: View {
    @ObservedObject var live: LiveFlow
    @EnvironmentObject private var face: FaceCaptureFlow
    @EnvironmentObject private var navigation: AppNavigation
    @Environment(\.scenePhase) private var scenePhase
    let onClose: () -> Void
    var body: some View {
        VcScreen(step: 3) {
            VcTitleBlock(title: "Đọc to câu sau")
            Text(live.voicePrompt ?? "Chưa nhận được câu đọc.").font(VcType.titleMedium)
            FaceSmallPreview(camera: face.camera).frame(width: 96, height: 128)
            #if DEBUG
            Text("IOS-04: \(face.lastFrameCount) frame · \(face.lastEvents.count) màu · \(face.lastRegionCount) mẫu vùng")
                .font(VcType.caption)
            Text("JPEG: \(live.frontalJpeg?.count ?? 0) bytes · AE/AWB đã khóa: \(face.lastQuality["ae_awb_locked"] == .bool(true) ? "có" : "không")")
                .font(VcType.caption)
            if case .number(let fps) = face.lastQuality["fps"] {
                Text("FPS: \(fps.formatted(.number.precision(.fractionLength(1))))").font(VcType.caption)
            }
            #endif
            VcBanner(text: "Bước thu giọng chưa được triển khai. Chưa gửi bản ghi âm và chưa có kết quả xác minh.", tone: .warning)
            VcSecondaryButton(title: "Quay lại ứng dụng ngân hàng") { face.cancel(); onClose() }
        }
        .onChange(of: scenePhase) { phase in
            if phase != .active { face.interrupt(); navigation.replaceTop(with: .interrupted) }
        }
    }
}
