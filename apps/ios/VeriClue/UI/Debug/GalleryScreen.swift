import SwiftUI

#if DEBUG
private struct GalleryGroup: Identifiable {
    let id = UUID()
    let title: String
    let items: [(String, Route)]
}

struct GalleryScreen: View {
    @EnvironmentObject private var navigation: AppNavigation
    @EnvironmentObject private var flow: DemoFlow
    @EnvironmentObject private var face: FaceCaptureFlow
    @EnvironmentObject private var voice: VoiceCaptureFlow
    @EnvironmentObject private var captures: CaptureFlows
    @Environment(\.vcColors) private var colors
    @State private var showFrontCameraCheckpoint = false
    @State private var showDeviceKeyCheckpoint = false
    @State private var ownedCaptureFiles: Int?

    private let groups = [
        GalleryGroup(title: "Bắt đầu", items: [("Màn chào", .splash), ("Đăng nhập / Đăng ký", .auth), ("Điều khoản và đồng ý", .terms)]),
        GalleryGroup(title: "Danh tính", items: [
            ("Số điện thoại", .phone),
            ("OTP", .otp), ("OTP nhập sai", .otpError), ("CCCD mặt trước", .idFront),
            ("CCCD bị lóa", .idFrontGlare),
            ("CCCD mặt sau", .idBack), ("Xem lại hai mặt CCCD", .idReview),
            ("Kiểm tra thông tin", .confirm), ("Sửa thông tin", .editInfo)
        ]),
        GalleryGroup(title: "Khuôn mặt", items: [("Chuẩn bị", .faceReady), ("Căn mặt", .framing), ("Giữ yên + nháy màu + chấm sáng", .holdStill), ("Quay đầu", .turnHead)]),
        GalleryGroup(title: "Giọng nói", items: [("Đọc câu", .voice), ("Đọc lại câu mới", .voiceAgain)]),
        GalleryGroup(title: "Kết quả", items: [
            ("Đang gửi", .uploading), ("Đang kiểm tra", .checking), ("Thành công", .success),
            ("Chờ duyệt", .review), ("Chụp lại", .retryQuality), ("Làm lại thử thách", .retryChallenge)
        ]),
        GalleryGroup(title: "Lỗi và gián đoạn", items: [
            ("Chưa cho camera", .errorCamera), ("Chưa cho micro", .errorMic), ("Mất mạng", .errorNetwork),
            ("Hết phiên", .errorSession), ("Dịch vụ không đáp ứng", .errorService), ("Thiết bị chưa đáp ứng", .errorDevice),
            ("Bị gián đoạn", .interrupted), ("Lượt quay hết hạn", .faceExpired), ("Không thu được giọng", .noVoice), ("Gửi thất bại", .uploadFailed),
            ("Kiểm tra lâu", .slow), ("Xác nhận dừng", .exitConfirm), ("Đã dừng", .stopped),
            ("Bỏ qua nháy màu", .flashSkipped), ("Không thành công", .deny), ("Cần khôi phục", .recoveryRequired)
        ]),
        GalleryGroup(title: "App ngân hàng (mô phỏng)", items: [("Mở tài khoản thành công", .bankOpened)])
    ]

    var body: some View {
        VcScreen {
            Text("Tất cả màn (bản demo giao diện)")
                .font(VcType.titleMedium)
                .foregroundStyle(colors.ink)
                .accessibilityIdentifier("debug-gallery-title")
            Button("Kiểm tra camera trước · IOS-04 (5.1–5.4)") { showFrontCameraCheckpoint = true }
                .font(VcType.label)
                .accessibilityIdentifier("debug-front-camera-checkpoint")
            ReceiptKeychainCheckpoint()
            Button("Kiểm tra khóa ký · DEBUG") { showDeviceKeyCheckpoint = true }
                .font(VcType.label)
                .accessibilityIdentifier("debug-device-key-checkpoint")
            Button("Kiểm tra file tạm · IOS-06") { ownedCaptureFiles = CaptureFileStore.ownedFileCount() }
                .font(VcType.label)
            if let count = ownedCaptureFiles {
                Text("File thu còn trong app: \(count) · Đã dọn lúc mở app: \(captures.startupCleanupCount)")
                    .font(VcType.caption)
            }
            if !voice.measurements.isEmpty {
                Text("Ba bản ghi giọng gần nhất · IOS-05").font(VcType.label)
                ForEach(Array(voice.measurements.enumerated()), id: \.offset) { index, item in
                    Text("\(index + 1). \(item.sessionID) · WAV \(item.wavSeconds.formatted(.number.precision(.fractionLength(3))))s · MP4 \(item.videoSeconds.formatted(.number.precision(.fractionLength(3))))s · offset \(item.offsetMs)ms · \(item.wavBytes)/\(item.videoBytes) bytes")
                        .font(VcType.caption).textSelection(.enabled)
                }
            }
            VStack(alignment: .leading, spacing: 8) {
                Text("Luồng").font(VcType.label).foregroundStyle(colors.muted)
                Picker("Luồng", selection: $flow.purpose) {
                    ForEach(Purpose.allCases) { purpose in Text(purpose.label).tag(purpose) }
                }
                .pickerStyle(.segmented)
            }
            VStack(alignment: .leading, spacing: 8) {
                Text("Nguồn kết quả").font(VcType.label).foregroundStyle(colors.muted)
                Picker("Nguồn kết quả", selection: $flow.useLiveAPI) {
                    Text("Giả lập trên máy").tag(false)
                    Text("API thật").tag(true)
                }
                .pickerStyle(.segmented)
                if flow.useLiveAPI {
                    VcBanner(text: "API: cấu hình Debug · kịch bản mock")
                    Picker("Kịch bản", selection: $flow.mockScenario) {
                        ForEach(flow.mockScenarios, id: \.self) { Text($0).tag($0) }
                    }
                }
            }
            VStack(alignment: .leading, spacing: 8) {
                Text("Kết quả mô phỏng sau bước kiểm tra (chỉ khi giả lập)").font(VcType.label).foregroundStyle(colors.muted)
                Picker("Kết quả", selection: $flow.outcome) {
                    ForEach(DemoOutcome.allCases) { Text($0.label).tag($0) }
                }
            }
            ForEach(groups) { group in
                VStack(alignment: .leading, spacing: 8) {
                    Text(group.title).font(VcType.section).foregroundStyle(colors.ink)
                    ForEach(group.items, id: \.1) { item in
                        Button {
                            flow.previewMode = true
                            navigation.go(item.1)
                        } label: {
                            HStack {
                                Text(item.0).font(VcType.bodySmall)
                                Spacer()
                                Image(systemName: "chevron.right").font(.caption)
                            }
                            .foregroundStyle(colors.accent)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 12)
                            .background(colors.surfaceSubtle, in: RoundedRectangle(cornerRadius: 10))
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
        .navigationTitle("Xem tất cả màn")
        .sheet(isPresented: $showFrontCameraCheckpoint) {
            FaceCameraCheckpointScreen(camera: face.camera, onClose: { showFrontCameraCheckpoint = false })
        }
        .sheet(isPresented: $showDeviceKeyCheckpoint) { DeviceKeychainCheckpoint() }
    }
}
#endif
