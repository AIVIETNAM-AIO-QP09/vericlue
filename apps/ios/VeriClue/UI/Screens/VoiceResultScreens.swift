import SwiftUI

struct VoiceScreen: View {
    var again = false
    let onFinished: () -> Void
    @State private var recording = false
    @State private var level = 0.2
    @Environment(\.vcColors) private var colors

    var body: some View {
        VcScreen(step: 3) {
            VcTitleBlock(
                title: again ? "Hãy đọc lại" : "Đọc to câu sau",
                bodyText: again ? "Chuyển đến nơi yên tĩnh hơn và đọc to, rõ ràng câu mới bên dưới." : nil
            )
            VcBanner(text: "Camera vẫn bật. Giữ mặt trong khung khi đọc.", systemImage: "camera")
            Text(again ? "“Tôi xác nhận mở tài khoản, mã số tám ba năm một.”" : "“Tôi xác nhận mở tài khoản, mã số bốn bảy hai chín.”")
                .font(VcType.titleMedium)
                .foregroundStyle(colors.ink)
                .multilineTextAlignment(.center)
                .frame(maxWidth: .infinity)
                .padding(20)
                .background(colors.surfaceSubtle, in: RoundedRectangle(cornerRadius: 16))
            if again {
                Text("Số lần đọc lại còn lại: 1").font(VcType.caption).foregroundStyle(colors.muted)
            } else {
                Text("Đọc rõ ràng, ở nơi yên tĩnh. Câu thay đổi mỗi lần.").font(VcType.caption).foregroundStyle(colors.muted)
            }
            WaveformView(level: level, active: recording)
            Button {
                if recording { onFinished() }
                recording.toggle()
            } label: {
                VStack(spacing: 10) {
                    Image(systemName: recording ? "stop.circle.fill" : "mic.circle.fill")
                        .font(.system(size: 72))
                    Text(recording ? "Dừng ghi âm" : "Bắt đầu ghi âm").font(VcType.button)
                    Text(recording ? "Đang nghe… bấm để dừng" : "Bấm để bắt đầu đọc").font(VcType.caption)
                }
                .foregroundStyle(recording ? colors.warn : colors.accent)
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.plain)
        }
        .task(id: recording) {
            while recording && !Task.isCancelled {
                level = Double.random(in: 0.18...0.95)
                try? await Task.sleep(nanoseconds: 120_000_000)
            }
        }
    }
}

private struct WaveformView: View {
    let level: Double
    let active: Bool
    @Environment(\.vcColors) private var colors

    var body: some View {
        HStack(alignment: .center, spacing: 5) {
            ForEach(0..<24, id: \.self) { index in
                Capsule()
                    .fill(active ? colors.accent : colors.border)
                    .frame(width: 5, height: active ? max(8, 48 * level * wave(index)) : 8)
                    .animation(.easeInOut(duration: 0.12), value: level)
            }
        }
        .frame(maxWidth: .infinity, minHeight: 60)
        .accessibilityLabel(active ? "Đang ghi âm" : "Chưa ghi âm")
    }

    private func wave(_ index: Int) -> Double {
        0.45 + abs(sin(Double(index) * 0.72)) * 0.55
    }
}

struct UploadingScreen: View {
    let onStop: () -> Void
    let onDone: () -> Void
    var autoAdvance: Bool
    @State private var completed = false

    var body: some View {
        MessageScreen(
            systemImage: "icloud.and.arrow.up",
            title: "Đang gửi dữ liệu",
            bodyText: "Đang gửi ảnh, video hoặc bản ghi của bước vừa thực hiện. Vui lòng giữ kết nối mạng.",
            secondary: ("Dừng xác minh", stop),
            spinning: true
        )
        .task {
            guard autoAdvance else { return }
            try? await Task.sleep(nanoseconds: 900_000_000)
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

struct CheckingScreen: View {
    let purpose: Purpose
    let onDone: () -> Void
    var autoAdvance: Bool
    @State private var processed = 0

    private var labels: [String] {
        purpose == .reauth ? ["Khuôn mặt", "Thiết bị"] : ["Ảnh giấy tờ", "Khuôn mặt", "Giọng nói"]
    }

    var body: some View {
        VcScreen(centered: true) {
            VcStatusBadge(systemImage: "checkmark.shield", spinning: true)
            VcTitleBlock(title: "Đang kiểm tra", bodyText: "Thường mất vài giây. Đừng tắt ứng dụng.", centered: true)
            VcChecklistCard(
                rows: labels.enumerated().map { index, label in
                    VcChecklistRow(systemImage: nil, label: label, state: index < processed ? .done : index == processed ? .doing : .waiting)
                }
            )
        }
        .task {
            guard autoAdvance else { return }
            for value in 0...labels.count {
                guard !Task.isCancelled else { return }
                processed = value
                try? await Task.sleep(nanoseconds: 520_000_000)
            }
            guard !Task.isCancelled else { return }
            onDone()
        }
    }
}

struct SuccessScreen: View {
    let purpose: Purpose
    var voiceChecked = true
    var liveVerification = false
    let onContinue: () -> Void

    var body: some View {
        VcScreen(centered: true) {
            VCSuccessEmblem()
            switch purpose {
            case .onboarding:
                VcTitleBlock(title: "Xác minh thành công", bodyText: "Đang quay lại ứng dụng ngân hàng…", centered: true)
                VcChecklistCard(
                    title: "Đã hoàn tất",
                    rows: (["Ảnh giấy tờ"] + FlowRules.checkedByServer(voiceChecked: voiceChecked))
                        .map { VcChecklistRow(systemImage: nil, label: $0, state: .done, trailing: "") }
                )
                VCSampleAccount()
            case .reauth:
                VcTitleBlock(title: "Đăng nhập thành công", bodyText: liveVerification ? "Danh tính của bạn đã được xác nhận." : "Danh tính của bạn đã được xác nhận. Thiết bị này đã được liên kết với tài khoản.", centered: true)
                if liveVerification {
                    VcChecklistCard(title: "Đã hoàn tất", rows: FlowRules.checkedByServer(voiceChecked: voiceChecked)
                        .map { VcChecklistRow(systemImage: nil, label: $0, state: .done, trailing: "") })
                } else {
                    VcChecklistCard(title: "Thiết bị đã liên kết", rows: [VcChecklistRow(systemImage: "iphone", label: "iPhone này", trailing: "Vừa xong")])
                }
            case .recovery:
                VcTitleBlock(title: "Khôi phục thành công", bodyText: "Danh tính của bạn đã được xác nhận.", centered: true)
                VcChecklistCard(title: "Bước tiếp theo", rows: [VcChecklistRow(systemImage: "key", label: "Đặt lại cách đăng nhập", trailing: "[chờ nhóm chốt]")])
            }
            VcPrimaryButton(title: purpose == .onboarding ? "Tiếp tục" : "Quay lại ứng dụng ngân hàng", action: onContinue)
        }
    }
}

struct ReviewScreen: View {
    let onBank: () -> Void

    var body: some View {
        MessageScreen(
            systemImage: "clock",
            title: "Hồ sơ đang được xác minh thêm",
            bodyText: "Nhân viên sẽ kiểm tra hồ sơ của bạn. Bạn sẽ nhận tin nhắn khi có kết quả.",
            primary: ("Quay lại ứng dụng ngân hàng", onBank),
            extra: AnyView(
                VcChecklistCard(
                    title: "Bạn sẽ nhận kết quả qua",
                    rows: [
                        VcChecklistRow(systemImage: "message", label: "Tin nhắn SMS"),
                        VcChecklistRow(systemImage: "bell", label: "Thông báo của ứng dụng ngân hàng")
                    ]
                )
            )
        )
    }
}

struct RetryQualityScreen: View {
    let onRetake: () -> Void

    var body: some View {
        MessageScreen(
            systemImage: "sun.max",
            title: "Ảnh chưa đủ rõ",
            bodyText: "Hãy ra chỗ sáng hơn và giữ điện thoại ngang tầm mặt.",
            primary: ("Chụp lại", onRetake),
            tone: .warning,
            extra: AnyView(Text("Còn 1 lần chụp lại").font(VcType.caption).foregroundStyle(.secondary))
        )
    }
}

struct RetryChallengeScreen: View {
    let onRetry: () -> Void

    var body: some View {
        MessageScreen(
            systemImage: "arrow.clockwise",
            title: "Chúng ta thử lại nhé",
            bodyText: "Giữ đầu yên, chỉ đưa mắt theo chấm sáng. Khi quay đầu, quay chậm rồi quay lại nhìn thẳng.",
            primary: ("Thử lại", onRetry),
            extra: AnyView(Text("Còn 1 lần thử").font(VcType.caption).foregroundStyle(.secondary))
        )
    }
}

struct MessageScreen: View {
    let systemImage: String
    let title: String
    let bodyText: String
    var primary: (String, () -> Void)? = nil
    var secondary: (String, () -> Void)? = nil
    var tone: VcTone = .info
    var spinning = false
    var extra: AnyView? = nil

    var body: some View {
        VcScreen(centered: true) {
            VcStatusBadge(systemImage: systemImage, tone: tone, spinning: spinning)
            VcTitleBlock(title: title, bodyText: bodyText, centered: true)
            if let extra { extra }
            if let primary { VcPrimaryButton(title: primary.0, action: primary.1) }
            if let secondary { VcSecondaryButton(title: secondary.0, action: secondary.1) }
        }
    }
}

struct MessageSpec {
    let systemImage: String
    let title: String
    let body: String
    let primary: String
    var secondary: String? = nil
    var tone: VcTone = .info

    static func forRoute(_ route: Route) -> MessageSpec? {
        switch route {
        case .errorCamera:
            MessageSpec(systemImage: "camera.fill.badge.ellipsis", title: "Chưa có quyền dùng camera", body: "Hãy cho phép dùng camera trong phần cài đặt của điện thoại rồi thử lại.", primary: "Thử lại")
        case .errorMic:
            MessageSpec(systemImage: "mic.slash", title: "Chưa có quyền dùng micro", body: "Hãy cho phép dùng micro trong phần cài đặt của điện thoại rồi thử lại.", primary: "Thử lại")
        case .errorNetwork:
            MessageSpec(systemImage: "wifi.slash", title: "Không kết nối được", body: "Hãy kiểm tra kết nối mạng rồi thử lại. Các bước bạn đã làm vẫn được giữ.", primary: "Thử lại")
        case .errorSession:
            MessageSpec(systemImage: "clock", title: "Phiên đã hết hạn", body: "Vì an toàn, phiên xác minh chỉ dùng trong một thời gian ngắn. Hãy bắt đầu lại từ ứng dụng ngân hàng.", primary: "Quay lại ứng dụng ngân hàng")
        case .errorService:
            MessageSpec(systemImage: "server.rack", title: "Tạm thời chưa thể xác minh", body: "Dịch vụ chưa phản hồi. Vui lòng thử lại sau. Lúc này chưa có kết quả xác minh.", primary: "Quay lại ứng dụng ngân hàng")
        case .errorDevice:
            MessageSpec(systemImage: "iphone.gen3", title: "Thiết bị chưa đáp ứng", body: "Camera hoặc micro chưa hoạt động ổn định, hoặc thiết bị chưa đáp ứng yêu cầu. Hãy kiểm tra quyền, đóng ứng dụng đang dùng thiết bị rồi thử lại.", primary: "Kiểm tra quyền truy cập", secondary: "Quay lại ứng dụng ngân hàng")
        case .interrupted:
            MessageSpec(systemImage: "video.slash", title: "Xác minh bị gián đoạn", body: "Camera bị ngắt hoặc ứng dụng đã rời màn hình. Hãy quay lại chuẩn bị và thực hiện lại.", primary: "Quay lại chuẩn bị", secondary: "Dừng xác minh")
        case .faceExpired:
            MessageSpec(systemImage: "clock", title: "Lượt quay đã hết hạn", body: "Thông tin của bạn vẫn được giữ. Hãy quay lại chuẩn bị và quay khuôn mặt lần nữa.", primary: "Quay lại chuẩn bị", secondary: "Dừng xác minh")
        case .noVoice:
            MessageSpec(systemImage: "mic.slash", title: "Chưa thu được giọng nói", body: "Bản ghi chưa dùng được hoặc micro đã bị ngắt. Hãy kiểm tra micro và chọn nơi yên tĩnh trước khi chuẩn bị đọc lại.", primary: "Chuẩn bị đọc lại", secondary: "Dừng xác minh")
        case .exitConfirm:
            MessageSpec(systemImage: "pause.circle", title: "Bạn muốn dừng xác minh?", body: "Bạn có thể quay lại chuẩn bị hoặc dừng phiên xác minh hiện tại.", primary: "Quay lại chuẩn bị", secondary: "Dừng xác minh")
        case .stopped:
            MessageSpec(systemImage: "stop.circle", title: "Đã dừng xác minh", body: "Phiên xác minh đã dừng. Khi sẵn sàng, bạn có thể bắt đầu lại từ ứng dụng ngân hàng.", primary: "Quay lại ứng dụng ngân hàng")
        case .flashSkipped:
            MessageSpec(systemImage: "iphone.gen3", title: "Cần xác minh theo cách khác", body: "Phần khuôn mặt cần màn hình đổi màu nhạt trong vài giây. Nếu bạn không xem được, vui lòng liên hệ ngân hàng để được hướng dẫn cách xác minh khác.", primary: "Quay lại ứng dụng ngân hàng")
        case .uploadFailed:
            MessageSpec(systemImage: "icloud.slash", title: "Chưa gửi được dữ liệu", body: "Hãy kiểm tra kết nối mạng rồi thử gửi lại. Dữ liệu chưa gửi xong chưa thể được kiểm tra.", primary: "Gửi lại", secondary: "Dừng xác minh")
        case .slow:
            MessageSpec(systemImage: "hourglass", title: "Đang mất nhiều thời gian hơn", body: "Hệ thống chưa trả kết quả xác minh. Bạn có thể tiếp tục chờ hoặc dừng phiên.", primary: "Tiếp tục chờ", secondary: "Dừng xác minh")
        case .deny:
            MessageSpec(systemImage: "xmark.shield", title: "Xác thực không thành công", body: "Vui lòng thử lại sau.", primary: "Quay lại ứng dụng ngân hàng")
        case .recoveryRequired:
            MessageSpec(systemImage: "iphone.and.arrow.forward", title: "Cần xác minh lại đầy đủ", body: "Thiết bị này chưa được liên kết. Hãy làm theo hướng dẫn khôi phục tài khoản trong ứng dụng ngân hàng.", primary: "Quay lại ứng dụng ngân hàng")
        default: nil
        }
    }
}
